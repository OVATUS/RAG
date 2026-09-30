# booking_bmt/models.py
from datetime import time, timedelta, datetime, timezone
from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
"""
    กติกา:
    - ผู้ใช้ 1 คน จองได้วันละ 1 ครั้ง
    - สนาม 1 แห่ง ต่อวัน/รอบ มีผู้จองได้คนเดียว
    """
User = get_user_model()

# รอบเวลา 3 ชั่วโมง (09, 12, 15, 18, 21)
SLOT_TIMES = [
    time(9, 0), time(12, 0), time(15, 0), time(18, 0), time(21, 0)
]
SLOT_CHOICES = [(t, t.strftime("%H:%M")) for t in SLOT_TIMES]


class Booking(models.Model):
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    court = models.ForeignKey("courts_bmt.Court", on_delete=models.CASCADE, related_name="bookings")

    booking_day = models.DateField()                    # วันที่ล้วน (YYYY-MM-DD)
    start_time = models.TimeField(choices=SLOT_CHOICES) # เวลาเริ่มรอบ (09/12/15/18/21)
    duration = models.PositiveIntegerField(default=180, help_text="ระยะเวลา (นาที) — คงที่ 180")
    status = models.CharField(
        max_length=20,
        choices=[("pending", "รออนุมัติ"), ("confirmed", "ยืนยันแล้ว"), ("cancelled", "ยกเลิก")],
        default="pending",
    )

    class Meta:
        ordering = ["-booking_day", "start_time"]
        constraints = [
            models.UniqueConstraint(fields=["user", "booking_day"], name="uniq_user_per_day"),
            models.UniqueConstraint(fields=["court", "booking_day", "start_time"], name="uniq_court_day_slot"),
            models.CheckConstraint(check=models.Q(duration=180), name="chk_duration_is_180"),
        ]
        indexes = [
            models.Index(fields=["user", "booking_day"]),
            models.Index(fields=["court", "booking_day", "start_time"]),
        ]

    def __str__(self):
        return f"[{self.booking_day} {self.start_time.strftime('%H:%M')}] {self.court} by {self.user}"

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.booking_day, self.start_time)

    @property
    def end_at(self) -> datetime:
        return self.start_at + timedelta(minutes=self.duration)

    def clean(self):
        if self.start_time not in SLOT_TIMES:
            raise ValidationError("เวลาเริ่มต้องเป็น 09:00, 12:00, 15:00, 18:00 หรือ 21:00 เท่านั้น")
        if self.duration != 180:
            raise ValidationError("ระบบรองรับการจองครั้งละ 3 ชั่วโมงเท่านั้น")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.full_clean()
            return super().save(*args, **kwargs)
    
    def clean(self):
        super().clean()
        today = timezone.now().date()
        if self.booking_day < today:
            raise ValidationError("ไม่สามารถจองย้อนหลังได้")
        if self.booking_day > today + timedelta(days=1):
            raise ValidationError("สามารถจองล่วงหน้าได้ไม่เกิน 1 วัน")