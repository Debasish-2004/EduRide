from django.db import models

# Create your models here.

class Route(models.Model):
    bus_no = models.CharField(max_length=50)
    route_name = models.CharField(max_length=100)
    coordinates = models.JSONField()
    waypoints = models.JSONField()

    def __str__(self):
        return f"{self.bus_no}"