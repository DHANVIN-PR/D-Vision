document.addEventListener("DOMContentLoaded", function() {
    console.log("D Vision website loaded");

    // Real-time Booking Notifications
    const bookingCount = document.querySelector("#booking-count");
    function checkNewBookings() {
        fetch("/get_new_bookings")
            .then(response => response.json())
            .then(data => {
                bookingCount.innerText = data.count;
            });
    }
    setInterval(checkNewBookings, 5000);

    // Booking Confirmation Alert
    const bookingForms = document.querySelectorAll("form[action^='/book_course']");
    bookingForms.forEach(form => {
        form.addEventListener("submit", function() {
            alert("✅ Course booked successfully!");
        });
    });

    // Delete Course Confirmation
    const deleteButtons = document.querySelectorAll(".delete-btn");
    deleteButtons.forEach(btn => {
        btn.addEventListener("click", function() {
            return confirm("⚠️ Are you sure you want to delete this course?");
        });
    });
});
