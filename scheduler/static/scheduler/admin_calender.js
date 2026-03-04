document.addEventListener('DOMContentLoaded', function() {
    console.log('Admin calendar loading...');
    
    var calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;
    
    window.calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        events: function(fetchInfo, successCallback, failureCallback) {
            console.log('Fetching events from', fetchInfo.startStr, 'to', fetchInfo.endStr);
            
            fetch(`/api/admin/bookings/?start=${fetchInfo.startStr}&end=${fetchInfo.endStr}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Events received:', data.bookings);
                    
                    // Add status as class for styling
                    data.bookings.forEach(event => {
                        event.className = [event.extendedProps.status];
                    });
                    
                    successCallback(data.bookings);
                })
                .catch(error => {
                    console.error('Error fetching events:', error);
                    failureCallback(error);
                });
        },
        eventClick: function(info) {
            console.log('Event clicked:', info.event);
            loadBookingDetails(info.event.id);
        },
        eventDidMount: function(info) {
            // Add tooltip with basic info
            const status = info.event.extendedProps.status;
            const customer = info.event.extendedProps.customer;
            info.el.title = `${customer} - Status: ${status}`;
        }
    });
    
    window.calendar.render();
    console.log('Calendar rendered');
});

function loadBookingDetails(bookingId) {
    console.log('Loading details for booking:', bookingId);
    
    const modal = new bootstrap.Modal(document.getElementById('bookingModal'));
    const detailsDiv = document.getElementById('bookingDetails');
    const modalHeader = document.getElementById('modalHeader');
    
    // Show loading
    detailsDiv.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    modal.show();
    
    // Fetch booking details 
    fetch(`/api/admin/bookings/?booking_id=${bookingId}`)
        .then(response => response.json())
        .then(data => {
            if (data.bookings && data.bookings.length > 0) {
                const booking = data.bookings[0].extendedProps;
                const event = data.bookings[0];
                
                // Set modal header color based on status
                modalHeader.className = `modal-header ${event.extendedProps.status}`;
                
                // Build details HTML
                detailsDiv.innerHTML = `
                    <div class="mb-3">
                        <span class="status-badge ${event.extendedProps.status}">
                            Status: ${event.extendedProps.status.toUpperCase()}
                        </span>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <h6>Customer Information</h6>
                            <p><strong>Name:</strong> ${event.extendedProps.customer}</p>
                            <p><strong>Phone:</strong> ${event.extendedProps.phone}</p>
                            <p><strong>Email:</strong> ${event.extendedProps.email || 'Not provided'}</p>
                        </div>
                        <div class="col-md-6">
                            <h6>Booking Details</h6>
                            <p><strong>Service:</strong> ${event.extendedProps.service}</p>
                            <p><strong>Staff:</strong> ${event.extendedProps.staff}</p>
                            <p><strong>Date:</strong> ${new Date(event.start).toLocaleDateString()}</p>
                            <p><strong>Time:</strong> ${new Date(event.start).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</p>
                        </div>
                    </div>
                    
                    ${event.extendedProps.note ? `
                    <div class="mb-3">
                        <h6>Admin Note</h6>
                        <p class="p-2 bg-light rounded">${event.extendedProps.note}</p>
                    </div>
                    ` : ''}
                    
                    <div class="action-buttons">
                        ${event.extendedProps.status === 'booked' ? `
                            <button class="btn btn-success" onclick="updateBookingStatus(${event.id}, 'confirm')">
                                Confirm Booking
                            </button>
                        ` : ''}
                        
                        ${event.extendedProps.status === 'confirmed' ? `
                            <button class="btn btn-success" onclick="updateBookingStatus(${event.id}, 'complete')">
                                Mark Completed
                            </button>
                        ` : ''}
                        
                        ${['booked', 'confirmed'].includes(event.extendedProps.status) ? `
                            <button class="btn btn-warning" onclick="openRescheduleModal(${event.id})">
                                Reschedule
                            </button>
                        ` : ''}
                        
                        ${['booked', 'confirmed'].includes(event.extendedProps.status) ? `
                            <button class="btn btn-danger" onclick="updateBookingStatus(${event.id}, 'cancel')">
                                Cancel
                            </button>
                        ` : ''}
                        
                        ${event.extendedProps.status === 'confirmed' ? `
                            <button class="btn btn-warning" onclick="updateBookingStatus(${event.id}, 'no-show')">
                                No Show
                            </button>
                        ` : ''}
                        
                        <button class="btn btn-info" onclick="openNoteModal(${event.id})">
                            Add Note
                        </button>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            detailsDiv.innerHTML = '<div class="alert alert-danger">Error loading booking details</div>';
        });
}

function updateBookingStatus(bookingId, action) {
    console.log(`Updating booking ${bookingId} with action: ${action}`);
    
    let url = `/api/admin/booking/${bookingId}/${action}/`;
    if (action === 'confirm') url = `/api/admin/booking/${bookingId}/confirm/`;
    if (action === 'cancel') url = `/api/admin/booking/${bookingId}/cancel/`;
    if (action === 'complete') url = `/api/admin/booking/${bookingId}/complete/`;
    if (action === 'no-show') url = `/api/admin/booking/${bookingId}/no-show/`;
    
    fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success message
            alert(`Booking ${action}ed successfully! ${data.email_sent ? 'Email sent to customer.' : ''}`);
            
            // Refresh calendar
            window.calendar.refetchEvents();
            
            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('bookingModal')).hide();
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error updating booking');
    });
}

function openRescheduleModal(bookingId) {
    // Close current modal
    bootstrap.Modal.getInstance(document.getElementById('bookingModal')).hide();
    
    // Open reschedule modal
    const modal = new bootstrap.Modal(document.getElementById('rescheduleModal'));
    document.getElementById('rescheduleBookingId').value = bookingId;
    document.getElementById('rescheduleDate').value = '';
    document.getElementById('rescheduleTime').innerHTML = '<option value="">First select a date</option>';
    document.getElementById('rescheduleTime').disabled = true;
    document.getElementById('rescheduleMessage').innerHTML = '';
    modal.show();
    
    // Set min date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('rescheduleDate').min = today;
}

// Handle date change in reschedule modal
document.getElementById('rescheduleDate')?.addEventListener('change', function() {
    const date = this.value;
    const bookingId = document.getElementById('rescheduleBookingId').value;
    const timeSelect = document.getElementById('rescheduleTime');
    
    if (!date || !bookingId) return;
    
    timeSelect.innerHTML = '<option value="">Loading...</option>';
    timeSelect.disabled = true;
    
    // Fetch available slots
    fetch(`/api/slots/?booking_id=${bookingId}&date=${date}`)
        .then(response => response.json())
        .then(data => {
            if (data.slots && data.slots.length > 0) {
                timeSelect.innerHTML = '<option value="">Select a time</option>';
                data.slots.forEach(slot => {
                    const option = document.createElement('option');
                    option.value = slot;
                    option.textContent = slot;
                    timeSelect.appendChild(option);
                });
                timeSelect.disabled = false;
            } else {
                timeSelect.innerHTML = '<option value="">No available slots</option>';
                document.getElementById('rescheduleMessage').innerHTML = 
                    '<div class="alert alert-warning mt-2">No available slots for this date</div>';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            timeSelect.innerHTML = '<option value="">Error loading slots</option>';
        });
});

// Confirm reschedule
document.getElementById('confirmReschedule')?.addEventListener('click', function() {
    const bookingId = document.getElementById('rescheduleBookingId').value;
    const date = document.getElementById('rescheduleDate').value;
    const time = document.getElementById('rescheduleTime').value;
    
    if (!date || !time) {
        alert('Please select both date and time');
        return;
    }
    
    fetch(`/api/admin/booking/${bookingId}/reschedule/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: JSON.stringify({
            new_date: date,
            new_time: time
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Booking rescheduled successfully!');
            bootstrap.Modal.getInstance(document.getElementById('rescheduleModal')).hide();
            window.calendar.refetchEvents();
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error rescheduling booking');
    });
});

function openNoteModal(bookingId) {
    // Close current modal
    bootstrap.Modal.getInstance(document.getElementById('bookingModal')).hide();
    
    // Open note modal
    const modal = new bootstrap.Modal(document.getElementById('noteModal'));
    document.getElementById('noteBookingId').value = bookingId;
    document.getElementById('noteText').value = '';
    modal.show();
}

// Save note
document.getElementById('saveNote')?.addEventListener('click', function() {
    const bookingId = document.getElementById('noteBookingId').value;
    const note = document.getElementById('noteText').value;
    
    fetch(`/api/admin/booking/${bookingId}/note/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: JSON.stringify({
            note: note
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Note added successfully!');
            bootstrap.Modal.getInstance(document.getElementById('noteModal')).hide();
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error adding note');
    });
}); 