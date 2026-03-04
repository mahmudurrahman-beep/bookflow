from django.contrib import admin
from .models import Service, Staff, WorkingHours, TimeOff, Booking, BusinessSettings
from .utils.email_utils import send_booking_status_update, send_booking_confirmation


# ─── Inlines ────────────────────────────────────────────────────────────────

class WorkingHoursInline(admin.TabularInline):
    model = WorkingHours
    extra = 7          # Show all 7 days ready to fill in
    max_num = 7        # Can't have more than 7 (one per weekday)
    fields = ['weekday', 'start_time', 'end_time', 'break_start', 'break_end']
    ordering = ['weekday']
    verbose_name = "Working Day"
    verbose_name_plural = "Working Hours (set one row per day the staff works)"


class TimeOffInline(admin.TabularInline):
    model = TimeOff
    extra = 1
    fields = ['date', 'start_time', 'end_time', 'reason']
    verbose_name = "Time Off Entry"
    verbose_name_plural = "Time Off"


# ─── Staff ──────────────────────────────────────────────────────────────────

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'is_active', 'working_days_summary']
    list_filter = ['is_active']
    inlines = [WorkingHoursInline, TimeOffInline]

    def working_days_summary(self, obj):
        """Show which weekdays the staff member has hours configured."""
        DAY_NAMES = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
        days = obj.working_hours.values_list('weekday', flat=True)
        if not days:
            return '⚠️ No working hours set — staff will have NO available slots!'
        return ', '.join(DAY_NAMES[d] for d in sorted(days))
    working_days_summary.short_description = 'Working Days'


# ─── Booking ─────────────────────────────────────────────────────────────────

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer_name', 'service', 'staff', 'start_datetime', 'status', 'customer_email']
    list_filter = ['status', 'service', 'staff']
    search_fields = ['customer_name', 'customer_phone', 'customer_email']
    readonly_fields = ['created_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        if change:  # Editing an existing booking
            original = Booking.objects.get(pk=obj.pk)
            old_status = original.status
            super().save_model(request, obj, form, change)
            if old_status != obj.status and obj.customer_email:
                try:
                    send_booking_status_update(obj, old_status, obj.status)
                    self.message_user(request, f"Status update email sent to {obj.customer_email}")
                except Exception as e:
                    self.message_user(request, f"Email failed: {e}", level='ERROR')
        else:  # New booking created via admin
            super().save_model(request, obj, form, change)
            if obj.customer_email:
                try:
                    send_booking_confirmation(obj)
                    self.message_user(request, f"Confirmation email sent to {obj.customer_email}")
                except Exception as e:
                    self.message_user(request, f"Email failed: {e}", level='ERROR')


# ─── Other models ────────────────────────────────────────────────────────────

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_minutes', 'price', 'is_active']
    list_filter = ['is_active']


@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    """
    Kept as standalone too, but managing via Staff page is easier.
    """
    list_display = ['staff', 'get_weekday_name', 'start_time', 'end_time', 'break_start', 'break_end']
    list_filter = ['staff', 'weekday']
    ordering = ['staff', 'weekday']

    def get_weekday_name(self, obj):
        return obj.get_weekday_display()
    get_weekday_name.short_description = 'Day'


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = ['staff', 'date', 'start_time', 'end_time', 'reason']
    list_filter = ['staff']
    ordering = ['date']


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    """Prevent creating multiple BusinessSettings rows by accident."""

    def has_add_permission(self, request):
        return not BusinessSettings.objects.exists() 