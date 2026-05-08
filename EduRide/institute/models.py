from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.contrib.auth.models import User

# Create your models here.

class Route(models.Model):
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
            models.UniqueConstraint(
                Lower("bus_no"),
                name="unique_route_bus_no_ci",
                violation_error_message="This bus number already exists.",
            ),
            models.UniqueConstraint(
                Lower("route_name"),
                name="unique_route_name_ci",
                violation_error_message="This route name already exists.",
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
