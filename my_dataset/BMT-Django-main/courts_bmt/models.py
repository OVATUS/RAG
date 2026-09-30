from django.db import models

class Court(models.Model):
    name = models.CharField(max_length=100)
    available = models.BooleanField(default=True)  # ว่างหรือไม่
    image = models.ImageField(upload_to="courts/", blank=True, null=True)  # เก็บรูปสนาม

    def __str__(self):
        return self.name
