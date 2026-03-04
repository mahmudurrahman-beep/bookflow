from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

# Set up logging for Render
logger = logging.getLogger(__name__)

def send_booking_confirmation(booking):
    """Send confirmation emails to customer and admin"""
    
    # Get site URL from settings (set this in Render environment variables)
    site_url = getattr(settings, 'SITE_URL', 'https://yourapp.onrender.com')
    admin_link = f"{site_url}/admin/scheduler/booking/{booking.id}/"
    
    try:
        # 1. Email to customer
        if booking.customer_email:
            customer_subject = f"Booking Confirmation - {booking.service.name} at BookFlow"
            customer_context = {
                'booking': booking,
                'customer_name': booking.customer_name,
                'customer_phone': booking.customer_phone,  # ⭐ Include phone
                'customer_email': booking.customer_email,
                'service': booking.service.name,
                'staff': booking.staff.name,
                'date': booking.start_datetime.strftime('%B %d, %Y'),
                'time': booking.start_datetime.strftime('%I:%M %p'),
                'duration': booking.service.duration_minutes,
                'booking_id': booking.id,  # ⭐ Include booking ID
                'site_url': site_url,
                'status_url': f"{site_url}/booking/{booking.id}/status/",
                'lookup_url': f"{site_url}/lookup/",
            }
            
            customer_html = render_to_string('scheduler/emails/customer_confirmation.html', customer_context)
            customer_text = f"""
            Hello {booking.customer_name},
            
            Your booking has been confirmed!
            
            Service: {booking.service.name}
            Staff: {booking.staff.name}
            Date: {booking.start_datetime.strftime('%B %d, %Y')}
            Time: {booking.start_datetime.strftime('%I:%M %p')}
            Duration: {booking.service.duration_minutes} minutes
            Booking ID: #{booking.id}
            
            View your booking: {site_url}/booking/{booking.id}/status/
            Look up your booking: {site_url}/lookup/
            
            Thank you for choosing BookFlow!
            """
            
            send_mail(
                subject=customer_subject,
                message=customer_text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[booking.customer_email],
                html_message=customer_html,
                fail_silently=False,
            )
            
            logger.info(f"Confirmation email sent to {booking.customer_email} for booking #{booking.id}")
        
    except Exception as e:
        logger.error(f"Failed to send customer confirmation email for booking #{booking.id}: {str(e)}")
        # Don't re-raise - let admin email still try to send
    
    try:
        # 2. Email to admin (if admin email is configured)
        admin_email = getattr(settings, 'ADMIN_EMAIL', None)
        if admin_email:
            admin_subject = f"New Booking: {booking.customer_name} - {booking.service.name}"
            admin_context = {
                'booking': booking,
                'customer_name': booking.customer_name,
                'customer_phone': booking.customer_phone,  # ⭐ Include phone
                'customer_email': booking.customer_email,
                'service': booking.service.name,
                'staff': booking.staff.name,
                'date': booking.start_datetime.strftime('%B %d, %Y'),
                'time': booking.start_datetime.strftime('%I:%M %p'),
                'duration': booking.service.duration_minutes,
                'booking_id': booking.id,  # ⭐ Include booking ID
                'admin_link': admin_link,
                'site_url': site_url,
                'status_url': f"{site_url}/booking/{booking.id}/status/",
            }
            
            admin_html = render_to_string('scheduler/emails/admin_notification.html', admin_context)
            admin_text = f"""
            New Booking Alert!
            
            Customer: {booking.customer_name}
            Phone: {booking.customer_phone}
            Email: {booking.customer_email}
            Service: {booking.service.name}
            Staff: {booking.staff.name}
            Date: {booking.start_datetime.strftime('%B %d, %Y')}
            Time: {booking.start_datetime.strftime('%I:%M %p')}
            Booking ID: #{booking.id}
            
            Customer Access Info:
            Customer will use Booking ID #{booking.id} and Phone ({booking.customer_phone}) to access their booking
            
            View in admin: {admin_link}
            Customer status page: {site_url}/booking/{booking.id}/status/
            """
            
            send_mail(
                subject=admin_subject,
                message=admin_text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_email],
                html_message=admin_html,
                fail_silently=False,
            )
            
            logger.info(f"Admin notification sent for booking #{booking.id}")
            
    except Exception as e:
        logger.error(f"Failed to send admin notification for booking #{booking.id}: {str(e)}")

def send_booking_status_update(booking, old_status, new_status):
    """Send email when booking status changes"""
    
    if not booking.customer_email:
        logger.warning(f"No customer email for booking #{booking.id}, skipping status update")
        return
    
    site_url = getattr(settings, 'SITE_URL', 'https://yourapp.onrender.com')
    
    try:
        subject = f"Booking Update: {booking.service.name} - Status: {new_status}"
        
        context = {
            'booking': booking,
            'customer_name': booking.customer_name,
            'customer_phone': booking.customer_phone,
            'customer_email': booking.customer_email,
            'old_status': old_status,
            'new_status': new_status,
            'service': booking.service.name,
            'staff': booking.staff.name,
            'date': booking.start_datetime.strftime('%B %d, %Y'),
            'time': booking.start_datetime.strftime('%I:%M %p'),
            'booking_id': booking.id,
            'site_url': site_url,
            'status_url': f"{site_url}/booking/{booking.id}/status/",
        }
        
        html_message = render_to_string('scheduler/emails/status_update.html', context)
        text_message = f"""
        Hello {booking.customer_name},
        
        Your booking status has been updated from '{old_status}' to '{new_status}'.
        
        Service: {booking.service.name}
        Staff: {booking.staff.name}
        Date: {booking.start_datetime.strftime('%B %d, %Y')}
        Time: {booking.start_datetime.strftime('%I:%M %p')}
        Booking ID: #{booking.id}
        
        View your booking: {site_url}/booking/{booking.id}/status/
        
        Thank you for choosing BookFlow!
        """
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.customer_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Status update email sent to {booking.customer_email} for booking #{booking.id}")
        
    except Exception as e:
        logger.error(f"Failed to send status update email for booking #{booking.id}: {str(e)}") 