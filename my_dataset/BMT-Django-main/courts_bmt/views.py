from datetime import date as date_cls, time
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.dateparse import parse_date
from django.db import IntegrityError, transaction
from .models import Court
from booking_bmt.models import Booking, SLOT_TIMES
from booking_bmt.forms import BookingForm
from django.core.exceptions import ValidationError

# แสดงสนาม
def court_list(request):
    courts = Court.objects.all()
    return render(request,'mainhome/dashboard.html', {"courts": courts})
    
#แสดงรายละเอียดสนาม + ตารางเวลาจอง 
@login_required
def court_detail(request, pk):
    court = get_object_or_404(Court, pk=pk)
    qd = request.GET.get("date")
    the_date = parse_date(qd) if qd else date_cls.today()

    bookings = Booking.objects.filter(
        court=court,
        booking_day=the_date,
        status__in=["pending", "confirmed"],
    )
    by_hour = {b.start_time.hour: b for b in bookings}

    form = BookingForm(initial={"day": the_date})
    return render(request, "mainhome/court_detail.html", {
        "court": court,
        "the_date": the_date,
        "slot_starts": [t.hour for t in SLOT_TIMES],
        "by_hour": by_hour,
        "form": form,
    })

# การจองสนาม
@login_required
def create_booking(request, pk):
    court = get_object_or_404(Court, pk=pk)
    if request.method != "POST":
        return redirect("court_detail", pk=pk)

    form = BookingForm(request.POST)
    if not form.is_valid():
        messages.error(request, "กรุณาเลือกวันที่และรอบเวลาให้ถูกต้อง")
        return redirect("court_detail", pk=pk)

    day, (h, m) = form.to_day_and_hm()

    try:
        with transaction.atomic():
            Booking.objects.create(
                user=request.user,
                court=court,
                booking_day=day,
                start_time=time(h, m),
                duration=180,
                status="pending",
            )
        messages.success(request, "จองสำเร็จแล้ว ")
    except IntegrityError:
        # ชน constraint: ผู้ใช้จองวันเดียวกันแล้ว หรือรอบนี้ถูกจองแล้ว
        messages.error(request, "วันนี้คุณได้ทำการจองไปแล้ว หรือรอบเวลานี้ถูกจองแล้ว ")
    except ValidationError as e:
        # มาจาก clean(): เช่น “จองล่วงหน้าเกิน 1 วัน”
        messages.error(request, e.messages[0] if e.messages else "ไม่สามารถทำรายการได้")

    return redirect("court_detail", pk=pk)

