# booking_bmt/forms.py
from django import forms
from .models import SLOT_TIMES

SLOT_CHOICES = [(t.strftime("%H:%M"), t.strftime("%H:%M")) for t in SLOT_TIMES]

class BookingForm(forms.Form):
    day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    slot = forms.ChoiceField(choices=SLOT_CHOICES)

    def to_day_and_hm(self):
        d = self.cleaned_data["day"]
        h, m = map(int, self.cleaned_data["slot"].split(":"))
        return d, (h, m)

class BookingRescheduleForm(BookingForm):
    """ใช้แก้ไข (Update) — รับค่าเริ่มต้นจาก instance"""
    def __init__(self, *args, **kwargs):
        instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)
        if instance is not None:
            self.fields["day"].initial = instance.booking_day
            self.fields["slot"].initial = instance.start_time.strftime("%H:%M")