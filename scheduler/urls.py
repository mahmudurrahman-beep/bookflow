from django.urls import path
from . import views

urlpatterns = [
    # ============= PUBLIC PAGES =============
    path('', views.index, name='index'),
    path('book/', views.book, name='book'),
    path('booking/<int:booking_id>/', views.confirmation, name='confirmation'),
    path('booking/<int:booking_id>/status/', views.booking_status, name='booking_status'),
    path('booking/<int:booking_id>/reschedule/', views.reschedule_booking, name='reschedule_booking'),
    path('lookup/', views.lookup_booking, name='lookup_booking'),
    path('api/admin/booking/<int:booking_id>/no-show/', views.api_admin_booking_no_show, name='api_booking_no_show'), 
    # ============= PUBLIC API =============
    path('api/services/', views.api_services, name='api_services'),
    path('api/staff/', views.api_staff, name='api_staff'),
    path('api/slots/', views.api_slots, name='api_slots'),
    path('api/public-calendar/', views.api_public_calendar, name='api_public_calendar'), 
    path('api/bookings/', views.api_create_booking, name='api_create_booking'),
    path('api/cancel-booking/<int:booking_id>/', views.api_cancel_booking, name='api_cancel_booking'),
    path('api/reschedule-booking/<int:booking_id>/', views.api_reschedule_booking, name='api_reschedule_booking'),
    path('api/booking/<int:booking_id>/ical/', views.ical_download, name='ical_download'),
    
    # ============= ADMIN PAGES =============
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/bookings/', views.admin_bookings, name='admin_bookings'),
    path('admin/services/', views.admin_services, name='admin_services'),
    path('admin/staff/', views.admin_staff, name='admin_staff'),
    path('admin/settings/', views.admin_settings, name='admin_settings'),
    
    # ============= ADMIN API =============
    path('api/admin/bookings/', views.api_admin_bookings, name='api_admin_bookings'),
    path('api/admin/booking/<int:booking_id>/confirm/', views.api_admin_booking_confirm, name='api_booking_confirm'),
    path('api/admin/booking/<int:booking_id>/cancel/', views.api_admin_booking_cancel, name='api_booking_cancel'),
    path('api/admin/booking/<int:booking_id>/complete/', views.api_admin_booking_complete, name='api_booking_complete'),
    path('api/admin/booking/<int:booking_id>/reschedule/', views.api_admin_booking_reschedule, name='api_booking_reschedule'),
    path('api/admin/booking/<int:booking_id>/note/', views.api_admin_booking_note, name='api_booking_note'),
] 
