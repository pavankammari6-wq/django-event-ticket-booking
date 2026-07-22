from django.contrib import admin
from .models import Event, Seat, Booking

admin.site.register(Event)
admin.site.register(Seat)
admin.site.register(Booking)