import json
import re

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Event, Seat, Booking


class EventListView(ListView):
    model = Event
    template_name = "booking/event_list.html"
    context_object_name = "events"
    ordering = ["date"]


class EventDetailView(DetailView):
    model = Event
    template_name = "booking/event_detail.html"
    context_object_name = "event"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["available_seats"] = self.object.seats.filter(is_booked=False)
        return context


@login_required
def book_seats(request, event_id):
    """
    Handles seat selection + booking creation.
    Uses select_for_update() inside an atomic transaction so two users
    can never book the same seat at the same time.
    """
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        seat_ids = request.POST.getlist("seat_ids")  # e.g. ["3", "4"]

        if not seat_ids:
            messages.error(request, "Please select at least one seat.")
            return redirect("event-detail", pk=event.id)

        try:
            with transaction.atomic():
                # lock the chosen seat rows until this transaction commits
                seats = (
                    Seat.objects.select_for_update()
                    .filter(id__in=seat_ids, event=event)
                )

                if seats.count() != len(seat_ids):
                    raise ValueError("One or more selected seats no longer exist.")

                if seats.filter(is_booked=True).exists():
                    raise ValueError("Sorry, one or more selected seats were just booked. Please choose again.")

                # mark seats as booked
                seats.update(is_booked=True)

                total_amount = event.price * len(seat_ids)

                booking = Booking.objects.create(
                    user=request.user,
                    event=event,
                    status="CONFIRMED",
                    total_amount=total_amount,
                )
                booking.seats.set(seats)

            messages.success(request, f"Booking confirmed! {len(seat_ids)} seat(s) reserved.")
            return redirect("booking-confirmation", booking_id=booking.id)

        except ValueError as e:
            messages.error(request, str(e))
            return redirect("event-detail", pk=event.id)

    return redirect("event-detail", pk=event.id)


@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).order_by("-booking_date")
    return render(request, "booking/my_bookings.html", {"bookings": bookings})


@login_required
def booking_confirmation(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    return render(request, "booking/confirmation.html", {"booking": booking})


@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if request.method == "POST" and booking.status == "CONFIRMED":
        with transaction.atomic():
            booking.seats.update(is_booked=False)
            booking.status = "CANCELLED"
            booking.save()
        messages.success(request, "Booking cancelled.")

    return redirect("my-bookings")


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


import anthropic
from django.conf import settings

@login_required
@require_POST
def chatbot_reply(request):
    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"reply": "Sorry, I didn't understand that."}, status=400)

    if not message:
        return JsonResponse({"reply": "Say something and I'll try to help!"})

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    system_prompt = """You are a ticket booking assistant. Based on the user's message,
respond with ONLY a JSON object (no other text) in this exact format:
{"intent": "show_events"} — if they want to see upcoming events
{"intent": "my_bookings"} — if they want to see their bookings
{"intent": "help"} — if they're asking what you can do
{"intent": "unknown"} — if it doesn't match any of the above
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        system=system_prompt,
        messages=[{"role": "user", "content": message}],
    )

    try:
        raw_text = response.content[0].text.strip()
        intent_data = json.loads(raw_text)
        intent = intent_data.get("intent", "unknown")
    except (json.JSONDecodeError, IndexError):
        intent = "unknown"

    # --- your existing logic decides what actually happens ---
    if intent == "show_events":
        events = Event.objects.order_by("date")[:5]
        if events:
            lines = [f"- {e.name} on {e.date.strftime('%d %b, %I:%M %p')} ({e.available_seats_count} seats left)" for e in events]
            reply = "Here are the upcoming events:\n" + "\n".join(lines)
        else:
            reply = "There are no events listed right now."

    elif intent == "my_bookings":
        bookings = Booking.objects.filter(user=request.user, status="CONFIRMED").order_by("-booking_date")[:5]
        if bookings:
            lines = [f"- {b.event.name}: seats {', '.join(s.seat_number for s in b.seats.all())}" for b in bookings]
            reply = "Your confirmed bookings:\n" + "\n".join(lines)
        else:
            reply = "You don't have any confirmed bookings yet."

    elif intent == "help":
        reply = "You can ask me to show events, check your bookings, or just say hi!"

    else:
        reply = "I'm not sure about that. Try asking about events or your bookings."

    return JsonResponse({"reply": reply})