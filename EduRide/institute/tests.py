from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth.models import User

from .models import Route, Institute


class RouteModelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="testadmin", password="password123")
        self.institute = Institute.objects.create(name="Test Institute", admin=self.admin)

    def test_duplicate_bus_number_is_rejected_case_insensitively(self):
        Route.objects.create(
            institute=self.institute,
            bus_no="ITER-01",
            route_name="Patia to Campus",
            coordinates=[[20.1, 85.8], [20.2, 85.9]],
            waypoints=[[20.1, 85.8], [20.2, 85.9]],
        )

        duplicate_bus = Route(
            institute=self.institute,
            bus_no="iter-01",
            route_name="Cuttack to Campus",
            coordinates=[[20.3, 85.7], [20.4, 85.6]],
            waypoints=[[20.3, 85.7], [20.4, 85.6]],
        )

        with self.assertRaises(ValidationError) as exc:
            duplicate_bus.full_clean()

        self.assertTrue(
            any("This bus number already exists" in msg for msg in exc.exception.messages)
        )

    def test_duplicate_route_name_is_rejected_case_insensitively(self):
        Route.objects.create(
            institute=self.institute,
            bus_no="ITER-01",
            route_name="Patia to Campus",
            coordinates=[[20.1, 85.8], [20.2, 85.9]],
            waypoints=[[20.1, 85.8], [20.2, 85.9]],
        )

        duplicate_route = Route(
            institute=self.institute,
            bus_no="ITER-02",
            route_name="patia to campus",
            coordinates=[[20.3, 85.7], [20.4, 85.6]],
            waypoints=[[20.3, 85.7], [20.4, 85.6]],
        )

        with self.assertRaises(ValidationError) as exc:
            duplicate_route.full_clean()

        self.assertTrue(
            any("This route name already exists" in msg for msg in exc.exception.messages)
        )

    def test_bus_number_and_route_name_are_trimmed(self):
        route = Route(
            institute=self.institute,
            bus_no="  ITER-01  ",
            route_name="  Patia to Campus  ",
            coordinates=[[20.1, 85.8], [20.2, 85.9]],
            waypoints=[[20.1, 85.8], [20.2, 85.9]],
        )

        route.full_clean()

        self.assertEqual(route.bus_no, "ITER-01")
        self.assertEqual(route.route_name, "Patia to Campus")

