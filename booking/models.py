from django.db import models
from django.contrib.auth.models import User


class Event(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    venue = models.CharField(max_length=200)
    date = models.DateTimeField()
    total_seats = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.date.strftime('%d %b %Y, %I:%M %p')}"

    @property
    def available_seats_count(self):
        return self.seats.filter(is_booked=False).count()

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating:
            seats = [
                Seat(event=self, seat_number=f"S{i+1}")
                for i in range(self.total_seats)
            ]
            Seat.objects.bulk_create(seats)


class Seat(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="seats")
    seat_number = models.CharField(max_length=10)
    is_booked = models.BooleanField(default=False)

    class Meta:
        unique_together = ("event", "seat_number")

    def __str__(self):
        return f"{self.event.name} - {self.seat_number}"


class Booking(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("CONFIRMED", "Confirmed"),
        ("CANCELLED", "Cancelled"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="bookings")
    seats = models.ManyToManyField(Seat)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    booking_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Booking #{self.id} - {self.user.username} - {self.event.name}"