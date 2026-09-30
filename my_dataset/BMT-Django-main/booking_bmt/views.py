from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from booking_bmt.models import Booking
from datetime import time
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from .forms import BookingRescheduleForm

@login_required
def cancel_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.status == "cancelled":
        messages.warning(request, "การจองนี้ถูกยกเลิกไปแล้ว")
    else:
        booking.status = "cancelled"
        booking.save()
        messages.success(request, "ยกเลิกการจองเรียบร้อยแล้ว")

    return redirect("booking_history")

def _owner_or_404(user, pk):
    return get_object_or_404(Booking, pk=pk, user=user)

# แก้ไขการจอง 
@login_required
def reschedule_booking(request, pk):
    booking = _owner_or_404(request.user, pk)

    #  ถ้าไม่ใช่ pending ห้ามแก้ไข
    if booking.status != "pending":
        messages.error(request, "ไม่สามารถแก้ไขได้หลังจากยืนยันแล้ว")
        return redirect("booking_history")

    if request.method == "POST":
        form = BookingRescheduleForm(request.POST, instance=booking)
        if form.is_valid():
            day, (h, m) = form.to_day_and_hm()
            try:
                with transaction.atomic():
                    booking.booking_day = day
                    booking.start_time = time(h, m)
                    booking.full_clean()
                    booking.save(update_fields=["booking_day", "start_time"])
                messages.success(request, "ปรับเวลา/วันจองเรียบร้อย ")
                return redirect("booking_history")
            except IntegrityError:
                messages.error(request, "วันนี้คุณได้ทำการจองไปแล้ว หรือรอบนี้ถูกจองแล้ว ")
            except ValidationError as e:
                messages.error(request, "; ".join(e.messages))
    else:
        form = BookingRescheduleForm(instance=booking)
    return render(request, "users_bmt/booking_edit.html", {"form": form, "booking": booking})

@login_required
def delete_booking(request, pk):
    """DELETE — ลบทิ้งจริง (hard delete) ของตัวเองเท่านั้น"""
    booking = _owner_or_404(request.user, pk)
    if request.method == "POST":
        booking.delete()
        messages.success(request, "ลบการจองแล้ว")
    return redirect("booking_history")
