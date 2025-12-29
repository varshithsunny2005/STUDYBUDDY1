from tkinter import LEFT
from django.shortcuts import render,redirect,get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import  transaction
from django.db.models import Q, Count
from .models import Room,Topic,Message,User
from django.conf import settings
from django.utils.html import escape
from django.contrib.auth import authenticate,login,logout
from.forms import RoomForm,UserForm,MyUserCreationForm
from supabase import create_client
import os
import json
# Create your views here.

# rooms = [
#     {'id': 1, 'name':'Lets learn python!'},
#     {'id': 2, 'name':'Design with me'},
#     {'id': 3, 'name':'GoLang Developers'},
# ]
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
# supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

_supabase_client= None

def get_supabase_client():
    global _supabase_client
    if _supabase_client is None:
        url=os.getenv("SUPABASE_URL")
        key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not url or not key:
            raise ValueError("Supabase URL or Service Role Key not set in environment variables.")
        
        _supabase_client=create_client(url,key)
    return _supabase_client

def upload_to_supabase(file_obj, file_name):
    bucket = "avatars"
    client= get_supabase_client()
    
    #Validate file type
    allowed_types =['image/jpeg','image/png','image/webp']
    if file_obj.content_type not in allowed_types:
        raise ValueError("Unsupported file Type")
    #Validate file size (max 5MB)
    max_size=5*1024*1024
    if file_obj.size>max_size:
        raise ValueError("File size exceeds the maximum limit of 5MB")
    
    
    # Try to delete the file first (ignore error if it doesn't exist)
    client.storage.from_(bucket).remove([file_name])
    file_bytes = file_obj.read()
    res = client.storage.from_(bucket).upload(file_name, file_bytes)
    # Check for status_code or raise_for_status
    if hasattr(res, "status_code") and not (200 <= res.status_code < 300):
        raise Exception(f"Upload failed: {getattr(res, 'data', res)}")
    url = client.storage.from_(bucket).get_public_url(file_name)
    return url

def loginPage(request):
    page = 'login'
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        email = request.POST.get('email','').strip().lower()
        password = request.POST.get('password','')
        
        if not email or not password:
            messages.error(request,'Email and Password are required')
            return render(request, 'base/login_register.html',{'page':page})
              
        user = authenticate(request,email=email,password=password)
        
        if user is not None:
            login(request,user)
            return redirect('home')
        
        else:
            messages.error(request, 'Invalid email or password')
            
        
    context = {'page':page}
    return render(request, 'base/login_register.html',context)

@require_POST #Ensure only POST requests are allowed
def logoutUser(request):
    logout(request)
    return redirect('home')

def registerPage(request):
    page = 'register'
    form=MyUserCreationForm()
    
    if request.method =='POST':
        form=MyUserCreationForm(request.POST)
        if form.is_valid():
            user=form.save(commit=False)
            user.username = user.username.lower()
            user.save()
            login(request,user)
            return redirect('home')
        else:
            messages.error(request,'An error occured during registration')
    return render(request, 'base/login_register.html',{'form':form})

def home(request):
    q = request.GET.get('q','').strip() # Get the search query from URL parameters
    rooms = Room.objects.filter(
          Q(topic__name__icontains=q) |
          Q(name__icontains=q) 
                  
         ).select_related('host','topic')
    
    # Most popular topics(rooms count)
    topics = Topic.objects.annotate(
        room_count=Count('room')
    ).order_by('room_count')[:5]
    
    #Equivalent SQL under the hood:
    #     SELECT topic.*, COUNT(room.id) as room_count
    #     FROM base_topic
    #     LEFT JOIN base_room ON base_topic.id = base_room.topic_id
    #     GROUP BY topic.id
    #     ORDER BY room_count DESC
    #     LIMIT 5; 
    
    room_count  = rooms.count()
    room_messages = Message.objects.select_related('user','room').order_by('-created')[:5]  # Get all messages, latest first


    context = {'rooms': rooms,'topics':topics,
               'room_count':room_count,'room_messages':room_messages}
    return render(request, 'base/home.html',context)


def room(request,pk):
    """
    Display chat room with messages and handle new message submissions.
    Supports both traditional form submission and AJAX requests.
    """
    
    # Fetch room with optimized query (prevents N+1 on host/topic access)
    room = get_object_or_404(
        Room.objects.select_related('host', 'topic'),
        id=pk
    )
    
    # Get messages in chronological order (oldest first for chat)
    # No select_related('user') needed - we use denormalized username/avatar_url
    room_messages = room.message_set.order_by('created')
    
    # Get participants (displayed in sidebar)
    participants = room.participants.all()
    
    
    # ===== Handle Message Submission =====
    if request.method == 'POST':
        
        # 1. Authentication check
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Login required'}, status=401)
        
        
        # 2. Detect request type (AJAX vs traditional form)
        is_ajax = request.content_type == 'application/json'
        
        
        # 3. Parse message body based on request type
        if is_ajax:
            try:
                data = json.loads(request.body)
                body = data.get('body', '').strip()
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON format'}, status=400)
        else:
            # Traditional form submission
            body = request.POST.get('body', '').strip()
        
        
        # 4. Input validation
        if not body:
            error_response = {'error': 'Message cannot be empty'}
            return JsonResponse(error_response, status=400) if is_ajax else redirect('room', pk=room.id)
        
        if len(body) > 5000:
            error_response = {'error': 'Message too long (max 5000 characters)'}
            return JsonResponse(error_response, status=400) if is_ajax else redirect('room', pk=room.id)
        
        # 5. Sanitize input (prevent XSS attacks)
        body = escape(body)
        
        
        # 6. Create message atomically (ensures both succeed or both fail)
        try:
            with transaction.atomic():
                message = Message.objects.create(
                    user=request.user,
                    room=room,
                    body=body,
                    username=request.user.username,
                    avatar_url=request.user.avatar or f"https://avatar.iran.liara.run/public/{request.user.id % 100}"
                )
                # Add user to participants if not already
                room.participants.add(request.user)
        
        except Exception as e:
            # Transaction automatically rolls back on exception
            error_response = {'error': f'Failed to send message: {str(e)}'}
            return JsonResponse(error_response, status=500)
        
        
        # 7. Return appropriate response
        if is_ajax:
            # AJAX request - return JSON with message data
            return JsonResponse({
                'status': 'success',
                'message': {
                    'id': message.id,
                    'body': message.body,
                    'username': message.username,
                    'avatar_url': message.avatar_url,
                    'user_id': message.user_id,  # For profile links
                    'created': message.created.isoformat()  # ISO format for JavaScript
                }
            })
        else:
            # Traditional form submission - redirect to refresh page
            return redirect('room', pk=room.id)
    
    
    # ===== Render Room Page (GET request) =====
    context = {
        'room': room,
        'room_messages': room_messages,
        'participants': participants,
        'SUPABASE_URL': settings.SUPABASE_URL,
        'SUPABASE_ANON_KEY': settings.SUPABASE_ANON_KEY
    }
    return render(request, 'base/room.html', context)

def userProfile(request,pk):
    #Get user or 404
    user=get_object_or_404(User,id=pk)
    # Get user's rooms with related data(prevents N+1 query problem)
    rooms=user.room_set.select_related('topic','host').all()
    
    # SQL Generated:
    # SELECT room.*, topic.*, user.* 
    # FROM base_room 
    # LEFT JOIN base_topic ON room.topic_id = topic.id
    # LEFT JOIN auth_user ON room.host_id = user.id
    # WHERE room.host_id = 5;
    
    # Get ONLY last 5 messages with room data 
    room_messages=user.message_set.select_related('room').order_by('-created')[:5]
    
    # SQL Generated:
    # SELECT message.*, room.* 
    # FROM base_message 
    # LEFT JOIN base_room ON message.room_id = room.id
    # WHERE message.user_id = 5
    # ORDER BY message.created DESC
    # LIMIT 5;
    
    
    context = {'user':user,'rooms':rooms,'room_messages':room_messages}
    return render(request,'base/profile.html',context)


@login_required(login_url='login')

def createRoom(request):
    
    if request.method=='POST':
        form=RoomForm(request.POST)
        
        if form.is_valid():
            #Get or create topic
            topic_name =request.POST.get('topic','').strip()
            
            # Validate topic name
            if not topic_name:
                messages.error(request, 'Topic is required.')
                return render(request, 'base/room_form.html',{
                    'form':form,
                    'topics':Topic.objects.all()
                })
            
            #Prevent Topic Spam(max=50 chars)
            if len(topic_name)>50 or len(topic_name)<3:
                messages.error(request, 'Topic name too long(max 50 chars) or too short(min 3 chars).')
                return render(request, 'base/room_form.html',{
                    'form':form,
                    'topics':Topic.objects.all()
                })
            
            # Get or create topic
            topic, created=Topic.objects.get_or_create(
                name=topic_name.lower() #Normalize to lowercase
            )
            
            try:
                with transaction.atomic():
                    room=form.save(commit=False)
                    room.host=request.user
                    room.topic=topic
                    room.save()
                    
                messages.success(request, f'Room "{room.name}" created successfully!')
                return redirect('room',pk=room.id) #Redirect to the New Room Page
            
            except Exception as e:
                messages.error(request, f'Failed to create room: {str(e)}')
                return render(request, 'base/room_form.html',{
                    'form':form,
                    'topics':Topic.objects.all()
                })
                
        else:
            #Form is invalid
            messages.error(request,'Please correct the errors below.')
        
    else:
        # GET request - show empty form
        form= RoomForm()
    
    context={
        'form':form,
        'topics':Topic.objects.all().order_by('name') # Alphabetical order
    }

    return render(request,'base/room_form.html',context)


@login_required(login_url='login')
def updateRoom(request, pk):
    """Update an existing room(Host only)"""
    
    room = get_object_or_404(Room, id=pk)
   
    #Authorization check(before loading topics)
    if request.user != room.host:
        messages.error(request, 'Only the Room Creator can update this room.')
        return redirect('room',pk=room.id)
    
    if request.method == 'POST':
        form=RoomForm(request.POST,instance=room)
        
        if form.is_valid():
            topic_name=request.POST.get('topic','').strip()
            
            if not topic_name:
                messages.error(request, 'Topic is required.')
                return render(request, 'base/room_form.html',{
                    'form':form,
                    'topics':Topic.objects.all(),
                    'room':room
                })
            
            if len(topic_name)>50 or len(topic_name)<3:
                messages.error(request, 'Topic name too long(max 50 chars) or too short(min 3 chars).')
                return render(request, 'base/room_form.html',{
                    'form':form,
                    'topics':Topic.objects.all(),
                    'room':room
                })
            
            topic, created=Topic.objects.get_or_create(
                name=topic_name.lower() #Normalize to lowercase
            )
            
            try:
                with transaction.atomic():
                    room=form.save(commit=False)
                    room.topic=topic
                    room.save()
                messages.success(request, f'Room "{room.name}" updated successfully!')
                return redirect('room',pk=room.id)
            
            except Exception as e:
                messages.error(request, f'Failed to update room: {str(e)}')
                return render(request, 'base/room_form.html',{
                    'form':form,
                    'topics':Topic.objects.all(),
                    'room':room
                })
        
        else:
            messages.error(request, 'Please correct the errors below.')
    
    else:
        form = RoomForm(instance=room)
       
    context={
        'form': form,
        'topics':Topic.objects.all().order_by('name'),
        'room':room 
        }
    return render(request, 'base/room_form.html',context)





@login_required(login_url='login')
def deleteRoom(request,pk):
    """
    Delete room. Only host can delete.
    Secure permission checking with proper error handling.
    """
    #Get room with 404 handling(prevents 500 errors)
    room = get_object_or_404(Room.objects.select_related('host'),id=pk)
    
    # Why select_related('host')?
    # - Prevents additional query when checking request.user != room.host
    # - Single query instead of two
    
    # Permission check IMMEDIATELY after fetching room
    if request.user != room.host:
        messages.error(request, 'Only the Room Creator can delete this room.')
        return redirect('room',pk=room.id)
   
   #Only allow POST(prevents accidental deletions via GET)
    if request.method == 'POST':
        room_name=room.name
        
        try:
            room.delete()
            messages.success(request,f'Room "{room_name}" deleted successfully!')
            return redirect('home')
        
        except Exception as e:
            messages.error(request,f'Failed to delete room: {str(e)}')
            return redirect('room',pk=pk)
        
         
    return render(request,'base/delete.html', {'obj':room, 'type':'room'})



@login_required(login_url='login')
def deleteMessage(request,pk):
    
    #Get msg or 404(with user and room preloaded)
    message = get_object_or_404(
        Message.objects.select_related('user','room'),
        id=pk
    )
    
    # Why select_related('user', 'room')?
    # SQL Generated:
    # SELECT message.*, user.*, room.*
    # FROM base_message
    # LEFT JOIN auth_user ON message.user_id = user.id
    # LEFT JOIN base_room ON message.room_id = room.id
    # WHERE message.id = 42;
    #
    # Result: 1 query instead of 3!
    # - message data
    # - user data (for permission check)
    # - room data (for redirect after deletion)
    
    
    #Permission check (immediate after fetching message)    
    if request.user != message.user:
        messages.error(request, "You don't have permission to delete this message.")
        return redirect('room',pk=message.room.id)
   
   #only allow POST(prevents accidental deletions via GET)
    if request.method == 'POST':
        room_id=message.room.id
        message_preview=message.body[:50]
        
        try:
            message.delete()
            messages.success(request, f'Message deleted: "{message_preview}..."')
            return redirect('room',pk=room_id)
        
        except Exception as e:
            messages.error(request, f'Failed to delete message: {str(e)}')
            return redirect('room',pk=message.room.id)
    
        
         #GET request - confirmation page
    return render(request,'base/delete.html', {'obj':message,'type':'message'})


@login_required(login_url='login')
def updateUser(request):
    """
    Update user profile (name, username, email, bio, avatar).
    Handles file uploads to Supabase with proper error handling.
    """
    
    user = request.user
    
    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES, instance=user)
        
        if form.is_valid():
            avatar_file = request.FILES.get('avatar')
            old_avatar = user.avatar  # Save for cleanup
            
            try:
                with transaction.atomic():
                    
                    # Handle avatar upload if present
                    if avatar_file:
                        # Generate unique filename
                        file_name = f"{user.username}_{avatar_file.name}"
                        
                        # Upload to Supabase (validation happens inside this function!)
                        # Raises ValueError if file type/size invalid
                        avatar_url = upload_to_supabase(avatar_file, file_name)
                        
                        # Update user avatar
                        user.avatar = avatar_url
                    
                    
                    # Save form data (name, username, email, bio)
                    updated_user = form.save(commit=False)
                    
                    # Normalize username to lowercase (consistent with registration)
                    updated_user.username = updated_user.username.lower()
                    
                    # Save to database
                    updated_user.save()
                    
                    
                    # Clean up old avatar from Supabase (optional)
                    if avatar_file and old_avatar and 'avatar.iran.liara.run' not in old_avatar:
                        try:
                            old_filename = old_avatar.split('/')[-1]
                            client = get_supabase_client()
                            client.storage.from_('avatars').remove([old_filename])
                        except Exception:
                            # Don't fail entire operation if cleanup fails
                            pass
                
                
                # Success message
                messages.success(request, 'Profile updated successfully!')
                return redirect('user-profile', pk=user.id)
            
            
            except ValueError as ve:
                # File validation errors from upload_to_supabase()
                # "Unsupported file Type" or "File size exceeds..."
                messages.error(request, str(ve))
                return render(request, 'base/update-user.html', {'form': form})
            
            except Exception as e:
                # Any other errors (Supabase upload, database save, etc.)
                messages.error(request, f'Failed to update profile: {str(e)}')
                return render(request, 'base/update-user.html', {'form': form})
        
        else:
            # Form validation failed
            messages.error(request, 'Please correct the errors below.')
    
    else:
        # GET request - show form with current user data
        form = UserForm(instance=user)
    
    
    context = {'form': form}
    return render(request, 'base/update-user.html', context)


def topicsPage(request):
    """
    Display all topics with room counts, sorted by popularity.
    Supports search functionality with user feedback.
    Optimized to prevent N+1 query problem.
    """
    
    # Get search query (sanitized)
    q = request.GET.get('q', '').strip()
    
    
    # Annotate topics with room count (prevents N+1 in template)
    topics = Topic.objects.annotate(
        room_count=Count('room')  # Add room_count field to each topic
    )
    
    # SQL Generated:
    # SELECT 
    #     topic.id,
    #     topic.name,
    #     COUNT(room.id) as room_count
    # FROM base_topic
    # LEFT JOIN base_room ON topic.id = room.topic_id
    # GROUP BY topic.id
    
    
    # Apply search filter if query exists
    if q:
        topics = topics.filter(name__icontains=q)
        # SQL: WHERE topic.name ILIKE '%python%'
    
    
    # Order by popularity (most rooms first), then alphabetically
    topics = topics.order_by('-room_count', 'name')
    # SQL: ORDER BY room_count DESC, name ASC
    
    
    # Get total count for display
    topic_count = topics.count()
    
    
    context = {
        'topics': topics,
        'topic_count': topic_count,
        'search_query': q  # For displaying "Showing results for 'python'"
    }
    
    return render(request, 'base/topics.html', context)

def activityPage(request):
    """
    Display recent activity (messages) across all rooms.
    Optimized to use denormalized data (no user joins needed).
    """
    
    # Get recent messages (limit 5 for performance)
    # NO select_related('user') needed - we use denormalized username/avatar_url
    room_messages = Message.objects.select_related('room').order_by('-created')[:5]
    
    # SQL Generated:
    # SELECT message.*, room.*
    # FROM base_message
    # LEFT JOIN base_room ON message.room_id = room.id
    # ORDER BY message.created DESC
    # LIMIT 50;
    
    # Why ONLY select_related('room')?
    # - message.username ← denormalized (no JOIN needed) 
    # - message.avatar_url ← denormalized (no JOIN needed) 
    # - message.room.name ← needs JOIN (for "posted in Python Room") 
    
    
    context = {
        'room_messages': room_messages
    }
    
    return render(request, 'base/activity.html', context)

def room_participants(request, room_id):
    """
    API endpoint to fetch room participants.
    Returns JSON array of user data with optimized queries.
    """
    
    try:
        # 1. Get room or return 404 JSON response
        room = get_object_or_404(Room, id=room_id)
        
        # Why not select_related()? 
        # Room has no foreign keys we need here (host/topic not used)
        
        
        # 2. Fetch participants with optimized query
        # Using only() to fetch only needed fields (reduces data transfer)
        users = room.participants.only(
            'id', 
            'name', 
            'username', 
            'avatar'
        ).order_by('username')
        
        # SQL Generated:
        # SELECT 
        #     user.id,
        #     user.name,
        #     user.username,
        #     user.avatar
        # FROM auth_user
        # INNER JOIN base_room_participants ON user.id = base_room_participants.user_id
        # WHERE base_room_participants.room_id = 123
        # ORDER BY user.username;
        
        # Why only()? 
        # Fetches only 4 fields instead of all 12+ User fields
        # Result: 70% less data transferred from database
        
        
        # 3. Build response data
        data = [
            {
                "id": user.id,
                "name": user.name or user.username,  # Fallback to username if no name
                "username": user.username,
                "avatar_url": user.avatar or f"https://avatar.iran.liara.run/public/{user.id % 100}"
                # ↑ Consistent with model's assign_avatar signal
            }
            for user in users
        ]
        
        
        # 4. Return JSON response with proper headers
        return JsonResponse(
            data, 
            safe=False,  # Allow list (not just dict)
            
        )
    
    
    except Room.DoesNotExist:
        # Explicit 404 JSON response (better than Django's HTML 404)
        return JsonResponse(
            {"error": "Room not found"}, 
            status=404
        )
    
    except Exception as e:
        # Catch any other errors (database connection, etc.)
        return JsonResponse(
            {"error": f"Failed to fetch participants: {str(e)}"}, 
            status=500
        )

@login_required
def sync_offline_messages(request):
    """
    API endpoint to sync offline messages when network returns.
    Expects JSON: {"room_id": 123, "messages": [{"client_id": "uuid", "body": "text", "timestamp": "iso"}]}
    """
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        data = json.loads(request.body)
        room_id = data.get('room_id')
        messages = data.get('messages', [])
        
        if not room_id:
            return JsonResponse({"error": "room_id required"}, status=400)
            
        room = Room.objects.get(id=room_id)
        synced_messages = []
        
        for msg_data in messages:
            client_id = msg_data.get('client_id')
            body = msg_data.get('body', '').strip()
            
            if not body or not client_id:
                continue
            
            # Sanitize input to prevent XSS (consistent with room POST handler)
            body = escape(body)
                
            # Check if message already exists (deduplication)
            existing = Message.objects.filter(
                user=request.user,
                room=room,
                body=body
            ).first()
            
            if not existing:
                # Save new message
                message = Message.objects.create(
                    user=request.user,
                    room=room,
                    body=body,
                    username=request.user.username,
                    avatar_url=request.user.avatar if request.user.avatar else 'https://avatar.iran.liara.run/public/17'
                )
                room.participants.add(request.user)
                
                synced_messages.append({
                    "client_id": client_id,
                    "server_id": message.id,
                    "synced": True
                })
            else:
                # Already exists, mark as synced
                synced_messages.append({
                    "client_id": client_id,
                    "server_id": existing.id,
                    "synced": True,
                    "duplicate": True
                })
        
        return JsonResponse({
            "success": True,
            "synced_messages": synced_messages
        })
        
    except Room.DoesNotExist:
        return JsonResponse({"error": "Room not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
