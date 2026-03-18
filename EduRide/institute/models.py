from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

# Create your models here.

class Route(models.Model):
    bus_no = models.CharField(max_length=50)
    route_name = models.CharField(max_length=100)
    coordinates = models.JSONField()
    waypoints = models.JSONField()

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
