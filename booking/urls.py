from django.urls import path
from . import views

urlpatterns = [
    path("", views.EventListView.as_view(), name="event-list"),
    path("event/<int:pk>/", views.EventDetailView.as_view(), name="event-detail"),
    path("event/<int:event_id>/book/", views.book_seats, name="book-seats"),
    path("my-bookings/", views.my_bookings, name="my-bookings"),
    path("booking/<int:booking_id>/confirmation/", views.booking_confirmation, name="booking-confirmation"),
    path("booking/<int:booking_id>/cancel/", views.cancel_booking, name="cancel-booking"),
    path("signup/", views.signup, name="signup"),
    path("chatbot/", views.chatbot_reply, name="chatbot-reply"),
]
