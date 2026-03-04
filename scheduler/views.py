import json
import pytz
from datetime import datetime, timedelta, date, time
from django.shortcuts import render, get_object_or_404, redirect  
from django.contrib import messages
from django.http import HttpResponse 
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Service, Staff, WorkingHours, TimeOff, Booking, BusinessSettings
from .utils.email_utils import send_booking_confirmation, send_booking_status_update
from django.db.models import Q 

# ============= PUBLIC PAGES =============

def index(request):
    """Home page"""
    return render(request, 'scheduler/public/index.html')

def book(request):
    """Booking page"""
    from datetime import date, timedelta
    
    today = date.today()
    max_date = today + timedelta(days=30)  
    
    return render(request, 'scheduler/public/book.html', {
        'today': today,
        'min_date': today,
        'max_date': max_date,
    })

def confirmation(request, booking_id):
    """Booking confirmation page"""
    booking = get_object_or_404(Booking, id=booking_id)
    return render(request, 'scheduler/public/confirmation.html', {
        'booking': booking
    })

# ============= PUBLIC API =============

def api_services(request):
    """Return list of active services"""
    services = Service.objects.filter(is_active=True).values('id', 'name', 'duration_minutes', 'price')
    return JsonResponse({'services': list(services)})

def api_staff(request):
    """Return list of active staff, optionally filtered by service"""
    service_id = request.GET.get('service')
    
    # Get all active staff
    staff = Staff.objects.filter(is_active=True)
    
    staff_list = []
    for s in staff:
        staff_list.append({
            'id': s.id,
            'name': s.name,
            'email': s.email
        })
    
    return JsonResponse({'staff': staff_list})

def api_slots(request):
    """Return available time slots for a given service, staff, and date"""
    service_id = request.GET.get('service')
    staff_id = request.GET.get('staff')
    date_str = request.GET.get('date')
    
    if not all([service_id, date_str]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        service = Service.objects.get(id=service_id, is_active=True)
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # If staff_id is provided and not empty, use that staff, otherwise get first available
        if staff_id and staff_id != '':
            staff = Staff.objects.get(id=staff_id, is_active=True)
            slots = generate_slots_for_staff(service, staff, target_date)
        else:
            # Get all active staff and combine slots
            slots = []
            for staff in Staff.objects.filter(is_active=True):
                staff_slots = generate_slots_for_staff(service, staff, target_date)
                slots.extend([f"{s} (with {staff.name})" for s in staff_slots])
        
        return JsonResponse({'slots': slots})
    
    except (Service.DoesNotExist, Staff.DoesNotExist, ValueError) as e:
        return JsonResponse({'error': str(e)}, status=400)

def api_public_calendar(request):
    """
    Returns booking activity for the current month + next month.
    Only exposes counts per day — no customer details.
    """
    from datetime import date
    import calendar

    today = date.today()
    # Cover current month and next month
    year  = today.year
    month = today.month

    # Build date range: today → end of next month
    if month == 12:
        end_year, end_month = year + 1, 1
    else:
        end_year, end_month = year, month + 1

    end_day = calendar.monthrange(end_year, end_month)[1]
    range_end = date(end_year, end_month, end_day)

    bookings = Booking.objects.filter(
        status__in=['booked', 'confirmed'],
        start_datetime__date__gte=today,
        start_datetime__date__lte=range_end,
    ).values('start_datetime', 'status')

    counts = {}  # { "2026-03-10": {"booked": 2, "confirmed": 1} }
    for b in bookings:
        d = b['start_datetime'].strftime('%Y-%m-%d')
        if d not in counts:
            counts[d] = {'booked': 0, 'confirmed': 0}
        counts[d][b['status']] = counts[d].get(b['status'], 0) + 1

    return JsonResponse({
        'counts': counts,
        'today': today.strftime('%Y-%m-%d'),
    }) 

def generate_slots_for_staff(service, staff, target_date):
    """Helper function to generate slots for a specific staff member"""
    try:
        settings = BusinessSettings.objects.first()
        if not settings:
            settings = BusinessSettings.objects.create()  # Create default settings

        if settings.max_days_ahead > 0:
            max_date = timezone.now().date() + timedelta(days=settings.max_days_ahead)
            if target_date > max_date:
                return []

        try:
            wh = WorkingHours.objects.get(staff=staff, weekday=target_date.weekday())
        except WorkingHours.DoesNotExist:
            return []

        # Combine date with times
        start_dt = datetime.combine(target_date, wh.start_time)
        end_dt = datetime.combine(target_date, wh.end_time)

        # Apply timezone — use is_dst=False to avoid AmbiguousTimeError on DST transitions
        tz = pytz.timezone(settings.timezone)
        try:
            start_dt = tz.localize(start_dt, is_dst=False)
            end_dt = tz.localize(end_dt, is_dst=False)
        except pytz.exceptions.NonExistentTimeError:
            # Time doesn't exist due to DST spring-forward — skip this date
            return []

        interval = timedelta(minutes=settings.slot_interval_minutes)
        buffer = timedelta(minutes=settings.buffer_minutes)
        duration = timedelta(minutes=service.duration_minutes)

        # ---- FIX: Compute notice_deadline ONCE before the loop ----
        notice_deadline = None
        if settings.min_notice_minutes > 0:
            notice_deadline = timezone.now() + timedelta(minutes=settings.min_notice_minutes)

        # Pre-fetch time-off and existing bookings for this date/staff (avoid N+1 queries)
        timeoff_list = list(TimeOff.objects.filter(staff=staff, date=target_date))
        day_start = tz.localize(datetime.combine(target_date, time(0, 0)), is_dst=False)
        day_end = tz.localize(datetime.combine(target_date, time(23, 59, 59)), is_dst=False)
        booked_slots = list(Booking.objects.filter(
            staff=staff,
            status__in=['booked', 'confirmed'],
            start_datetime__lt=day_end + buffer,
            end_datetime__gt=day_start - buffer,
        ))

        slots = []
        current = start_dt

        while current + duration <= end_dt:
            slot_end = current + duration

            # ---- FIX: Check minimum notice OUTSIDE the booking-conflict block ----
            if notice_deadline and current < notice_deadline:
                current += interval
                continue

            # Check breaks
            if wh.break_start and wh.break_end:
                try:
                    break_start = tz.localize(datetime.combine(target_date, wh.break_start), is_dst=False)
                    break_end = tz.localize(datetime.combine(target_date, wh.break_end), is_dst=False)
                except pytz.exceptions.NonExistentTimeError:
                    break_start = break_end = None

                if break_start and current < break_end and slot_end > break_start:
                    current = break_end
                    continue

            # Check time off (using pre-fetched list)
            conflict = False
            for to in timeoff_list:
                if to.start_time and to.end_time:
                    try:
                        to_start = tz.localize(datetime.combine(target_date, to.start_time), is_dst=False)
                        to_end = tz.localize(datetime.combine(target_date, to.end_time), is_dst=False)
                    except pytz.exceptions.NonExistentTimeError:
                        conflict = True
                        break
                    if current < to_end and slot_end > to_start:
                        conflict = True
                        break
                else:
                    conflict = True  # Full day off
                    break

            if conflict:
                current += interval
                continue

            # Check existing bookings (using pre-fetched list)
            has_conflict = any(
                b.start_datetime < slot_end + buffer and b.end_datetime > current - buffer
                for b in booked_slots
            )

            if not has_conflict:
                slots.append(current.strftime('%H:%M'))

            current += interval

        return slots

    except Exception as e:
        # Log unexpected errors (DST edge cases, bad timezone config, etc.)
        print(f"[generate_slots_for_staff] Error for staff={staff.id} date={target_date}: {e}")
        return []

@csrf_exempt
def api_create_booking(request):
    """Create a new booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        email = data.get('email', '').strip()
        if not email:
            return JsonResponse({'error': 'Email address is required'}, status=400)
        
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return JsonResponse({'error': 'Invalid email format'}, status=400)
        
        # Extract staff name if it was combined with slot
        time_str = data.get('time')
        staff = None
        
        if ' (with ' in time_str:
            # Format: "14:00 (with John)"
            time_str, staff_name = time_str.split(' (with ')
            staff_name = staff_name.rstrip(')')
            staff = Staff.objects.get(name=staff_name, is_active=True)
        else:
            staff_id = data.get('staff')
            if staff_id:
                staff = Staff.objects.get(id=staff_id, is_active=True)
            else:
                # Auto-assign first available staff
                staff = Staff.objects.filter(is_active=True).first()
        
        service = Service.objects.get(id=data.get('service'), is_active=True)
        date_str = data.get('date')
        time_str = time_str or data.get('time')
        
        # Parse datetime
        start_datetime = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
        end_datetime = start_datetime + timedelta(minutes=service.duration_minutes)
        
        # Apply timezone
        settings = BusinessSettings.objects.first()
        if settings:
            tz = pytz.timezone(settings.timezone)
            start_datetime = tz.localize(start_datetime)
            end_datetime = tz.localize(end_datetime)
        
        # Check if slot is still available
        existing = Booking.objects.filter(
            staff=staff,
            status__in=['booked', 'confirmed'],
            start_datetime__lt=end_datetime,
            end_datetime__gt=start_datetime
        )
        
        if existing.exists():
            return JsonResponse({'error': 'This slot is no longer available'}, status=400)
        
        # Create booking with required email
        booking = Booking.objects.create(
            service=service,
            staff=staff,
            customer_name=data.get('name'),
            customer_phone=data.get('phone'),
            customer_email=email, 
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            status='booked'
        )
        
        # Send email notifications
        try:     
            send_booking_confirmation(booking)
        except Exception as e:
            print(f"Email sending failed: {e}")
        
        return JsonResponse({
            'success': True,
            'booking_id': booking.id,
            'message': 'Booking created successfully'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400) 

# ============= ADMIN PAGES =============

@login_required
def admin_dashboard(request):
    """Admin calendar dashboard"""
    return render(request, 'scheduler/admin/dashboard.html')

@login_required
def admin_bookings(request):
    """Admin bookings list view"""
    return render(request, 'scheduler/admin/bookings.html')

@login_required
def admin_services(request):
    """Admin services management"""
    return render(request, 'scheduler/admin/services.html')

@login_required
def admin_staff(request):
    """Admin staff management"""
    return render(request, 'scheduler/admin/staff.html')

@login_required
def admin_settings(request):
    """Admin business settings"""
    return render(request, 'scheduler/admin/settings.html')

# ============= ADMIN API =============

@login_required
def api_admin_bookings(request):
    """Get bookings for calendar display"""
    booking_id = request.GET.get('booking_id')
    start = request.GET.get('start')
    end = request.GET.get('end')
    
    # If specific booking requested
    if booking_id:
        bookings = Booking.objects.filter(id=booking_id).select_related('service', 'staff')
    elif start and end:
        bookings = Booking.objects.filter(
            start_datetime__gte=start,
            start_datetime__lte=end
        ).select_related('service', 'staff')
    else:
        bookings = Booking.objects.all().select_related('service', 'staff')[:100]
    
    events = []
    for booking in bookings:
        color_map = {
            'booked': '#ffc107',      # yellow
            'confirmed': '#28a745',   # green
            'completed': '#6c757d',   # gray
            'cancelled': '#dc3545',   # red
            'no_show': '#fd7e14',     # orange
        }
        
        events.append({
            'id': booking.id,
            'title': f"{booking.customer_name} - {booking.service.name}",
            'start': booking.start_datetime.isoformat(),
            'end': booking.end_datetime.isoformat(),
            'color': color_map.get(booking.status, '#17a2b8'),
            'extendedProps': {
                'status': booking.status,
                'customer': booking.customer_name,
                'phone': booking.customer_phone,
                'email': booking.customer_email,
                'service': booking.service.name,
                'staff': booking.staff.name,
                'note': booking.admin_note
            }
        })
    
    return JsonResponse({'bookings': events}) 

@login_required
@csrf_exempt
def api_admin_booking_confirm(request, booking_id):
    """Confirm a booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    booking = get_object_or_404(Booking, id=booking_id)
    old_status = booking.status
    booking.status = 'confirmed'
    booking.save()
    
    response_data = {'success': True}
    if booking.customer_email:
        try:
            send_booking_status_update(booking, old_status, 'confirmed')
            response_data['email_sent'] = True
        except Exception as e:
            response_data['email_sent'] = False
            response_data['email_error'] = str(e)
            print(f"Email sending failed: {e}")
    else:
        response_data['email_sent'] = False
        response_data['email_status'] = 'No email provided'
    
    return JsonResponse(response_data) 

@login_required
@csrf_exempt
def api_admin_booking_cancel(request, booking_id):
    """Cancel a booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    booking = get_object_or_404(Booking, id=booking_id)
    old_status = booking.status
    booking.status = 'cancelled'
    booking.save()
    
    response_data = {'success': True}
    if booking.customer_email:
        try:
            send_booking_status_update(booking, old_status, 'cancelled')
            response_data['email_sent'] = True
        except Exception as e:
            response_data['email_sent'] = False
            response_data['email_error'] = str(e)
            print(f"Email sending failed: {e}")
    else:
        response_data['email_sent'] = False
        response_data['email_status'] = 'No email provided'
    
    return JsonResponse(response_data)

@login_required
@csrf_exempt
def api_admin_booking_complete(request, booking_id):
    """Mark booking as completed"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    booking = get_object_or_404(Booking, id=booking_id)
    old_status = booking.status
    booking.status = 'completed'
    booking.save()
    
    response_data = {'success': True}
    if booking.customer_email:
        try:
            send_booking_status_update(booking, old_status, 'completed')
            response_data['email_sent'] = True
        except Exception as e:
            response_data['email_sent'] = False
            response_data['email_error'] = str(e)
            print(f"Email sending failed: {e}")
    else:
        response_data['email_sent'] = False
        response_data['email_status'] = 'No email provided'
    
    return JsonResponse(response_data) 

@login_required
@csrf_exempt
def api_admin_booking_no_show(request, booking_id):
    """Mark booking as no-show"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    booking = get_object_or_404(Booking, id=booking_id)
    old_status = booking.status
    booking.status = 'no_show'
    booking.save()

    response_data = {'success': True}
    if booking.customer_email:
        try:
            send_booking_status_update(booking, old_status, 'no_show')
            response_data['email_sent'] = True
        except Exception as e:
            response_data['email_sent'] = False
            print(f"Email failed: {e}")

    return JsonResponse(response_data) 

@login_required
@csrf_exempt
def api_admin_booking_reschedule(request, booking_id):
    """Reschedule a booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        booking = get_object_or_404(Booking, id=booking_id)
        
        new_date = datetime.fromisoformat(data.get('new_date'))
        new_time = datetime.strptime(data.get('new_time'), '%H:%M').time()
        
        new_start = datetime.combine(new_date.date(), new_time)
        new_end = new_start + timedelta(minutes=booking.service.duration_minutes)
        
        # Check availability
        existing = Booking.objects.filter(
            staff=booking.staff,
            status__in=['booked', 'confirmed'],
            start_datetime__lt=new_end,
            end_datetime__gt=new_start
        ).exclude(id=booking_id)
        
        if existing.exists():
            return JsonResponse({'error': 'New slot is not available'}, status=400)
        
        booking.start_datetime = new_start
        booking.end_datetime = new_end
        booking.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@csrf_exempt
def api_admin_booking_note(request, booking_id):
    """Add note to booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        booking = get_object_or_404(Booking, id=booking_id)
        booking.admin_note = data.get('note', '')
        booking.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400) 
     
def lookup_booking(request):
    """Page to look up a booking by ID and phone"""
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        phone = request.POST.get('phone')
        
        # Clean the inputs
        try:
            booking_id = int(booking_id)
        except (ValueError, TypeError):
            messages.error(request, "Invalid booking ID format")
            return render(request, 'scheduler/public/lookup_booking.html')
        
        # Look for booking with matching ID and phone
        try:
            booking = Booking.objects.get(
                Q(id=booking_id) & 
                (Q(customer_phone=phone) | Q(customer_phone__endswith=phone[-10:]))
            )
            # Redirect to status page
            return redirect('booking_status', booking_id=booking.id)
        except Booking.DoesNotExist:
            messages.error(request, "No booking found with that ID and phone number")
        except Booking.MultipleObjectsReturned:
            messages.error(request, "Multiple bookings found. Please contact support.")
    
    return render(request, 'scheduler/public/lookup_booking.html')

def booking_status(request, booking_id):
    """Public view for customers to check booking status"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Get related upcoming bookings for same customer (optional)
    customer_bookings = Booking.objects.filter(
        customer_phone=booking.customer_phone
    ).exclude(id=booking.id).order_by('-start_datetime')[:3]
    
    return render(request, 'scheduler/public/booking_status.html', {
        'booking': booking,
        'customer_bookings': customer_bookings,
        'can_cancel': booking.status in ['booked', 'confirmed'],
        'can_reschedule': booking.status in ['booked', 'confirmed'],
    }) 
  
@csrf_exempt
def api_cancel_booking(request, booking_id):
    """Allow customers to cancel their own booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Only allow cancellation of booked or confirmed bookings
    if booking.status not in ['booked', 'confirmed']:
        return JsonResponse({'error': 'This booking cannot be cancelled'}, status=400)
    
    old_status = booking.status
    booking.status = 'cancelled'
    booking.save()
    
    # Send email notification
    if booking.customer_email:
        try:            
            send_booking_status_update(booking, old_status, 'cancelled')
        except Exception as e:
            print(f"Email failed: {e}")
    
    return JsonResponse({'success': True}) 

def reschedule_booking(request, booking_id):
    """Page for customers to reschedule their booking"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Only allow rescheduling for certain statuses
    if booking.status not in ['booked', 'confirmed']:
        messages.error(request, "This booking cannot be rescheduled")
        return redirect('booking_status', booking_id=booking.id)
    
    return render(request, 'scheduler/public/reschedule.html', {
        'booking': booking,
        'today': timezone.now().date()
    })

@csrf_exempt
def api_reschedule_booking(request, booking_id):
    """API for customers to reschedule their own booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        booking = get_object_or_404(Booking, id=booking_id)
        
        # Verify booking can be rescheduled
        if booking.status not in ['booked', 'confirmed']:
            return JsonResponse({'error': 'This booking cannot be rescheduled'}, status=400)
        
        # Parse new datetime
        new_date = datetime.strptime(data.get('new_date'), '%Y-%m-%d').date()
        new_time = datetime.strptime(data.get('new_time'), '%H:%M').time()
        new_start = datetime.combine(new_date, new_time)
        new_end = new_start + timedelta(minutes=booking.service.duration_minutes)
        
        # Apply timezone
        settings = BusinessSettings.objects.first()
        if settings:
            tz = pytz.timezone(settings.timezone)
            new_start = tz.localize(new_start)
            new_end = tz.localize(new_end)
        
        # Check availability
        existing = Booking.objects.filter(
            staff=booking.staff,
            status__in=['booked', 'confirmed'],
            start_datetime__lt=new_end,
            end_datetime__gt=new_start
        ).exclude(id=booking_id)
        
        if existing.exists():
            return JsonResponse({'error': 'Selected time is no longer available'}, status=400)
        
        # Update booking 
        booking.start_datetime = new_start
        booking.end_datetime = new_end
        booking.save()
        
        # Send notification emails
        if booking.customer_email:
            try:
                send_booking_status_update(booking, 'rescheduled', 'rescheduled')
            except Exception as e:
                print(f"Email failed: {e}")
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def ical_download(request, booking_id):
    """Generate iCal file for booking"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Create iCal content
    cal_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//BookFlow//EN
BEGIN:VEVENT
UID:{booking.id}@bookflow.com
DTSTAMP:{timezone.now().strftime('%Y%m%dT%H%M%S')}
DTSTART:{booking.start_datetime.strftime('%Y%m%dT%H%M%S')}
DTEND:{booking.end_datetime.strftime('%Y%m%dT%H%M%S')}
SUMMARY:{booking.service.name} with {booking.staff.name}
DESCRIPTION:Booking #{booking.id} for {booking.customer_name}
LOCATION:BookFlow Business Address
END:VEVENT
END:VCALENDAR"""
    
    response = HttpResponse(cal_content, content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename=booking_{booking.id}.ics'
    return response 