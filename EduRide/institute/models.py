import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import User

# Create your models here.


class Institute(models.Model):
    """
    Represents a registered institute/school/college.

    Each institute gets a unique code (e.g. EDU-A3X7K2) that drivers and
    students use to join during signup.  The institute admin creates this
    record automatically when they sign up.

    PAYMENT GATE
    -------------
    has_paid must be True before the admin can manage buses.
    """

    name = models.CharField(max_length=200)

    # Auto-generated, human-readable code.
    # editable=False prevents anyone from changing it via admin forms.
    institute_code = models.CharField(
        max_length=12, unique=True, editable=False
    )

    # The Django User who is the admin of this institute.
    # OneToOneField ensures one admin per institute and vice-versa.
    admin = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="institute",
    )

    # Payment gate: institute must pay before accessing bus features.
    has_paid = models.BooleanField(default=False)

    # Razorpay order ID for the payment (stored so we can verify later).
    razorpay_order_id = models.CharField(max_length=100, blank=True, default="")

    # Razorpay payment ID (stored after successful verification for refunds/audit).
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.institute_code:
            self.institute_code = self._generate_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_code():
        """
        Generate a unique, human-friendly code like 'EDU-A3X7K2'.

        Uses uuid4 to get random hex chars, takes 6, uppercases them.
        Keeps trying until we get one that doesn't collide (extremely unlikely).
        """
        while True:
            code = "EDU-" + uuid.uuid4().hex[:6].upper()
            if not Institute.objects.filter(institute_code=code).exists():
                return code

    def __str__(self):
        return f"{self.name} ({self.institute_code})"


@receiver(pre_delete, sender=Institute)
def delete_institute_members(sender, instance, **kwargs):
    """
    When an Institute is deleted, also delete all member Users (students & drivers).

    WHY is this needed?
    -------------------
    The cascade chain is: Admin User → Institute → UserProfile (via FK CASCADE).
    But deleting a UserProfile does NOT delete the associated User, because the
    FK points from UserProfile → User (not the other way around).
    This leaves orphaned User records for students and drivers.

    This signal closes that gap by deleting member Users BEFORE the Institute
    is removed, which then cascades to their UserProfiles as well.
    """
    # Delete all Users whose profile is linked to this institute.
    # Excludes the admin user (they're already being deleted via CASCADE).
    User.objects.filter(
        profile__institute=instance,
    ).exclude(
        id=instance.admin_id,
    ).delete()


class Route(models.Model):
    # ── Which institute owns this route ──
    institute = models.ForeignKey(
        Institute,
        on_delete=models.CASCADE,
        related_name="routes",
    )

    bus_no = models.CharField(max_length=50)
    route_name = models.CharField(max_length=100)
    coordinates = models.JSONField()
    waypoints = models.JSONField()

    # Which driver is assigned to this bus. null=True means "unassigned".
    # unique=True ensures one driver can only be assigned to one route.
    # related_name="assigned_route" lets you do: user.assigned_route to get the route.
    driver = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_route",
        limit_choices_to={"profile__role": "driver"},
    )

    # Is the bus currently running on the road?
    # Only the assigned driver can toggle this.
    is_active = models.BooleanField(default=False)

    # ── Live GPS location (updated by the driver's browser every ~5 seconds) ──
    # These are NULL when the bus is offline or no GPS data has been sent yet.
    live_latitude = models.FloatField(null=True, blank=True)
    live_longitude = models.FloatField(null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # In a multi-institute system, bus_no and route_name only need
            # to be unique WITHIN the same institute.
            models.UniqueConstraint(
                Lower("bus_no"), "institute",
                name="unique_route_bus_no_per_institute",
                violation_error_message="This bus number already exists in your institute.",
            ),
            models.UniqueConstraint(
                Lower("route_name"), "institute",
                name="unique_route_name_per_institute",
                violation_error_message="This route name already exists in your institute.",
            ),
        ]

    def clean(self):
        self.bus_no = (self.bus_no or "").strip()
        self.route_name = (self.route_name or "").strip()

        if not self.bus_no:
            raise ValidationError({"bus_no": "Bus number is required."})

        if not self.route_name:
            raise ValidationError({"route_name": "Route name is required."})

    def __str__(self):
        return f"{self.bus_no}"


class BusSchedule(models.Model):
    """
    A departure time for a bus route. REQUIRED — every route must have ≥ 1.

    Examples:
        "Morning Pickup" at 10:00 AM
        "Evening Return" at 5:00 PM
    """
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    label = models.CharField(
        max_length=100,
        help_text='E.g. "Morning Pickup", "Evening Return"',
    )
    departure_time = models.TimeField()

    class Meta:
        ordering = ["departure_time"]

    def __str__(self):
        return f"{self.route.bus_no} — {self.label} ({self.departure_time:%I:%M %p})"


class BusStop(models.Model):
    """
    A named stop along a bus route. REQUIRED — every route must have ≥ 2 stops.

    ETA is auto-calculated from the distance between consecutive stops
    assuming an average bus speed of 40 km/h (Haversine formula).
    """
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name="stops",
    )
    name = models.CharField(max_length=200)
    latitude = models.FloatField()
    longitude = models.FloatField()
    order_index = models.PositiveIntegerField(
        help_text="Order of this stop along the route (0 = first stop).",
    )
    # Auto-computed: cumulative minutes from the first stop.
    # First stop = 0, subsequent stops = sum of (distance / 40 km/h) segments.
    eta_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Auto-computed cumulative minutes from departure.",
    )

    class Meta:
        ordering = ["order_index"]
        unique_together = ["route", "order_index"]

    def __str__(self):
        return f"{self.name} (Stop #{self.order_index})"
