import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
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
