# users_bmt/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile
import re

PHONE_REGEX = re.compile(r"^\+?\d{8,15}$")  

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(
        required=True,
        max_length=20,
        help_text="เบอร์โทร",
    )

    class Meta:
        model = User
        fields = ("username", "email", "phone", "password1", "password2")

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if not PHONE_REGEX.match(phone):
            raise forms.ValidationError("รูปแบบเบอร์โทรไม่ถูกต้อง")
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            UserProfile.objects.create(user=user, phone=self.cleaned_data["phone"])
        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base = "mt-1 block w-full rounded-lg border-gray-300 focus:border-indigo-500 focus:ring-indigo-500"
        self.fields["username"].widget = forms.TextInput(attrs={"class": base, "placeholder": "ชื่อผู้ใช้"})
        self.fields["email"].widget = forms.EmailInput(attrs={"class": base, "placeholder": "อีเมล (ถ้ามี)"})
        self.fields["password1"].widget = forms.PasswordInput(attrs={"class": base, "placeholder": "รหัสผ่าน"})
        self.fields["password2"].widget = forms.PasswordInput(attrs={"class": base, "placeholder": "ยืนยันรหัสผ่าน"})

