from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
# # Create your models here.

class User(AbstractUser):
    name = models.CharField(max_length=200, null=True)
    email = models.EmailField(unique=True)
    bio = models.TextField(null=True)
    # avatar = models.URLField(null=True, default="https://avatar.iran.liara.run/public/17")  # <-- changed
    avatar=models.URLField(null=True,blank=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
   
   
    
@receiver(post_save,sender=User)
def assign_avatar(sender,instance,created,**kwargs):
    """
    Automatically assigns a unique default avatar URL
    when a new user is created and has no avatar set.
    """
    if created and not instance.avatar:
        # instance.avatar=f"https://avatar.iran.liara.run/public/{instance.id % 100}"
        # instance.save(update_fields=['avatar'])
         User.objects.filter(pk=instance.pk).update(
            avatar=f"https://avatar.iran.liara.run/public/{instance.id % 100}"
        )
         instance.refresh_from_db()  # Update in-memory object

class Topic(models.Model):
    name = models.CharField(max_length=200,unique=True)
    
    def __str__(self):
        return self.name
    
    

class Room(models.Model):
    host= models.ForeignKey(User, on_delete=models.SET_NULL,null=True)
    topic=models.ForeignKey(Topic, on_delete=models.SET_NULL,null=True)
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=5000,null=True,blank=True)
    participants =models.ManyToManyField(User,related_name='participants',blank=True)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-updated','-created']
        indexes=[
            models.Index(fields=['updated']),
            models.Index(fields=['created']),
        ]
    
    def __str__(self):
        return self.name
     
    

class Message(models.Model):
    user= models.ForeignKey(User, on_delete=models.CASCADE)
    room= models.ForeignKey(Room, on_delete=models.CASCADE) 
    body=models.TextField()
    username = models.CharField(max_length=150)
    avatar_url = models.CharField(max_length=255)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-updated','-created']
        indexes=[
            models.Index(fields=['room','-created']),
           # models.Index(fields=['user','-created']),
            models.Index(fields=['-created']),
        ]
        
    def __str__(self):
        return self.body[0:50]
    
