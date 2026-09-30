# users_bmt/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import RegisterForm
from django.contrib.auth.decorators import login_required
from booking_bmt.models import Booking
from django.contrib.auth import logout
from django.shortcuts import render, get_object_or_404
from .models import UserProfile

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ")
            return redirect("login")
    else:
        form = RegisterForm()
    return render(request, "users_bmt/register.html", {"form": form})

# ประวัติการจอง
@login_required
def booking_history_view(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-booking_day', '-start_time')
    return render(request, "users_bmt/booking_history.html", {"bookings": bookings})

# โปรไฟล์ user
@login_required
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    return render(request, "users_bmt/profile.html", {
        "user": request.user,
        "profile": profile
    })

@login_required
def deactivate_confirm_view(request):
    # หน้าให้ผู้ใช้ยืนยันก่อน
    return render(request, "users_bmt/deactivate_confirm.html")

#ลบผู้ใช้ 
@login_required
def deactivate_me_view(request):
    if request.method != "POST":
        return redirect("deactivate_confirm")
    user = request.user
    user.is_active = False
    user.save(update_fields=["is_active"])
    logout(request)  # ออกจากระบบทันที
    messages.success(request, "บัญชีของคุณถูกปิดการใช้งานแล้ว")
    return redirect("login") 
    
@login_required
def edit_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        phone = request.POST.get("phone", "").strip()
        if phone:
            profile.phone = phone
        profile.save()
        return redirect("profile")  

    return render(request, "users_bmt/edit_profile.html", {
        "profile": profile,
        "user": request.user,
    })