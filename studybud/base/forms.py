from django import forms
from django.forms import ModelForm
from .models import Room,User
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm




class MyUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['name','username','email','password1','password2']
        
        
class RoomForm(ModelForm):
    class Meta:
        model = Room 
        fields = ['name','description']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Enter room name...',
                'maxlength': '200',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Describe your room...',
                'rows': 4,
                'maxlength': '5000'
            })
        }
        exclude = ['host', 'participants']

    def clean_name(self):
        """Validate room name"""
        name=self.cleaned_data.get('name','').strip()
        
        if not name:
            raise ValidationError('Room name is Required')
        
        if len(name)<3:
            raise ValidationError('Room name must be at least 3 characters long')
        
        #Prevent XSS
        
        dangerous_chars=['<','>','"',"'",'`']
        if any(char in name for char in dangerous_chars):
            raise ValidationError('Room name contains invalid characters')
        
        return name
    
    def clean_description(self):
        """Validate Description"""
        description=self.cleaned_data.get('description','').strip()
        
        if len(description)>5000:
            raise ValidationError('Description too long(max 5000 characters)')
        
        return description
        
        
class UserForm(ModelForm):
    avatar = forms.CharField(required=False, widget=forms.HiddenInput())
    class Meta:
        model = User
        fields = ['avatar','name','username','email','bio']