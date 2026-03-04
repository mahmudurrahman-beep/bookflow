// In DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Booking.js loaded'); // Debug log
    
    const serviceSelect = document.getElementById('service');
    const staffSelect = document.getElementById('staff');
    const dateInput = document.getElementById('date');
    const timeSelect = document.getElementById('time');
    const form = document.getElementById('bookingForm');
    const messageDiv = document.getElementById('message');

    // Set min date to today
    const today = new Date().toISOString().split('T')[0];
    dateInput.min = today;
    dateInput.value = ''; // Clear any default value

    // Initially disable staff and date until service is selected
    staffSelect.disabled = true;
    dateInput.disabled = true;
    timeSelect.disabled = true;

    // Load services on page load
    fetch('/api/services/')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log('Services loaded:', data); // Debug log
            // Clear existing options except the first one
            serviceSelect.innerHTML = '<option value="">Choose a service...</option>';
            
            data.services.forEach(s => {
                const option = document.createElement('option');
                option.value = s.id;
                option.textContent = s.name;
                option.dataset.duration = s.duration_minutes;
                serviceSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading services:', error);
            showMessage('Error loading services. Please refresh the page.', 'danger');
        });

    // When service changes, load staff
    serviceSelect.addEventListener('change', function() {
        const serviceId = this.value;
        console.log('Service selected:', serviceId); // Debug log
        
        // Reset dependent fields
        staffSelect.innerHTML = '<option value="">Loading staff...</option>';
        staffSelect.disabled = true;
        dateInput.disabled = true;
        dateInput.value = '';
        timeSelect.innerHTML = '<option value="">First select a date...</option>';
        timeSelect.disabled = true;
        
        if (!serviceId) {
            staffSelect.innerHTML = '<option value="">First select a service...</option>';
            return;
        }
        
        // Load staff for this service
        fetch(`/api/staff/?service=${serviceId}`)
            .then(response => response.json())
            .then(data => {
                console.log('Staff loaded:', data); // Debug log
                staffSelect.innerHTML = '<option value="">Any available staff</option>';
                
                if (data.staff && data.staff.length > 0) {
                    data.staff.forEach(s => {
                        const option = document.createElement('option');
                        option.value = s.id;
                        option.textContent = s.name;
                        staffSelect.appendChild(option);
                    });
                    staffSelect.disabled = false;
                } else {
                    staffSelect.innerHTML = '<option value="">No staff available</option>';
                }
                
                // Enable date selection
                dateInput.disabled = false;
            })
            .catch(error => {
                console.error('Error loading staff:', error);
                staffSelect.innerHTML = '<option value="">Error loading staff</option>';
            });
    });

    // When staff changes, enable date (but don't load slots yet)
    staffSelect.addEventListener('change', function() {
        console.log('Staff selected:', this.value); // Debug log
        if (serviceSelect.value) {
            dateInput.disabled = false;
            // Clear any previously loaded times
            timeSelect.innerHTML = '<option value="">Select a date first...</option>';
            timeSelect.disabled = true;
        }
    });

    // When date changes, load available slots
    dateInput.addEventListener('change', function() {
        const serviceId = serviceSelect.value;
        const staffId = staffSelect.value;
        const date = this.value;
        
        console.log('Selected date:', date);
        console.log('Day of week (JS):', new Date(date).getDay()); // 0=Sun, 6=Sat
        console.log('Day of week (Python style):', new Date(date).getDay() === 0 ? 6 : new Date(date).getDay() - 1);
        console.log('Date selected:', date, 'Service:', serviceId, 'Staff:', staffId); // Debug log
        
        // Reset time select
        timeSelect.innerHTML = '<option value="">Loading available times...</option>';
        timeSelect.disabled = true;
        
        if (!serviceId || !date) {
            timeSelect.innerHTML = '<option value="">Select service and date first</option>';
            return;
        }
        
        // Build URL with query parameters
        let url = `/api/slots/?service=${serviceId}&date=${date}`;
        if (staffId && staffId !== '') {
            url += `&staff=${staffId}`;
        }
        
        console.log('Fetching slots from:', url); // Debug log
        
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                console.log('Slots received:', data); // Debug log
                
                if (data.slots && data.slots.length > 0) {
                    timeSelect.innerHTML = '<option value="">Select a time...</option>';
                    data.slots.forEach(t => {
                        const option = document.createElement('option');
                        option.value = t;
                        option.textContent = t;
                        timeSelect.appendChild(option);
                    });
                    timeSelect.disabled = false;
                } else {
                    timeSelect.innerHTML = '<option value="">No available slots for this date</option>';
                    showMessage('No available slots for this date. Please choose another date.', 'warning');
                }
            })
            .catch(error => {
                console.error('Error loading slots:', error);
                timeSelect.innerHTML = '<option value="">Error loading slots</option>';
                showMessage('Error loading available times. Please try again.', 'danger');
            });
    });

    // Handle form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        console.log('Form submitted'); // Debug log
        
        // Validate all fields
        if (!serviceSelect.value) {
            showMessage('Please select a service', 'warning');
            return;
        }
        if (!dateInput.value) {
            showMessage('Please select a date', 'warning');
            return;
        }
        if (!timeSelect.value) {
            showMessage('Please select a time', 'warning');
            return;
        }
        if (!document.getElementById('name').value) {
            showMessage('Please enter your name', 'warning');
            return;
        }
        if (!document.getElementById('phone').value) {
            showMessage('Please enter your phone number', 'warning');
            return;
        }
        
        // ⭐ NEW: Validate email is required
        const email = document.getElementById('email').value;
        if (!email) {
            showMessage('Email address is required for confirmation', 'warning');
            return;
        }
        
        // Validate email format
        const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!emailPattern.test(email)) {
            showMessage('Please enter a valid email address', 'warning');
            return;
        }
        
        // Prepare data
        const formData = {
            service: serviceSelect.value,
            staff: staffSelect.value || null,
            date: dateInput.value,
            time: timeSelect.value,
            name: document.getElementById('name').value,
            phone: document.getElementById('phone').value,
            email: email,  // Now required
        };
        
        console.log('Submitting booking:', formData); // Debug log
        
        // Disable submit button to prevent double submission
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Booking...';
        
        // Submit booking
        fetch('/api/bookings/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
            body: JSON.stringify(formData),
        })
        .then(response => response.json())
        .then(data => {
            console.log('Booking response:', data); // Debug log
            
            if (data.booking_id) {
                // Success - redirect to confirmation page
                window.location.href = `/booking/${data.booking_id}/`;
            } else {
                // Error - show message
                showMessage(data.error || 'Error creating booking', 'danger');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Book Appointment';
            }
        })
        .catch(error => {
            console.error('Error creating booking:', error);
            showMessage('Error creating booking. Please try again.', 'danger');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Book Appointment';
        });
    });

    // Helper function to show messages
    function showMessage(text, type) {
        messageDiv.innerHTML = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${text}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>`;
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            const alert = messageDiv.querySelector('.alert');
            if (alert) {
                alert.remove();
            }
        }, 5000);
    }
}); 