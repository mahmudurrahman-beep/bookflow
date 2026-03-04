from django.db import models
from django.contrib.auth.models import User
import pytz

class Service(models.Model):
    name = models.CharField(max_length=100)
    duration_minutes = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Staff(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField() 
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class WorkingHours(models.Model):
    # Python weekday(): 0=Monday, 1=Tuesday, ..., 6=Sunday  ← matches date.weekday()
    WEEKDAYS = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='working_hours')
    weekday = models.IntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ('staff', 'weekday')

class TimeOff(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)  # null = full day
    end_time = models.TimeField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)

class BusinessSettings(models.Model):
    timezone = models.CharField(max_length=50, default='UTC')
    slot_interval_minutes = models.PositiveIntegerField(default=15)
    buffer_minutes = models.PositiveIntegerField(default=0)
    min_notice_minutes = models.PositiveIntegerField(default=0)
    max_days_ahead = models.PositiveIntegerField(default=30)

    class Meta:
        verbose_name_plural = "Business settings"

class Booking(models.Model):
    STATUS_CHOICES = [
        ('booked', 'Booked'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No-show'),
    ]
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT)
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='booked')
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer_name} - {self.start_datetime}" 