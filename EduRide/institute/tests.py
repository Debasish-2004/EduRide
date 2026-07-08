import json
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from student.models import UserProfile

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


class InstituteBugFixTests(TestCase):
    def setUp(self):
        # Create institute admin and profile
        self.admin = User.objects.create_user(username="instadmin", password="password123")
        self.institute = Institute.objects.create(name="Test Institute", admin=self.admin, has_paid=True)
        self.profile = UserProfile.objects.create(
            user=self.admin,
            role="institute_admin",
            institute=self.institute,
        )

        # Create driver users
        self.driver1 = User.objects.create_user(username="driver1", password="password123")
        UserProfile.objects.create(user=self.driver1, role="driver", institute=self.institute)

        self.driver2 = User.objects.create_user(username="driver2", password="password123")
        UserProfile.objects.create(user=self.driver2, role="driver", institute=self.institute)

        # Create route
        self.route = Route.objects.create(
            institute=self.institute,
            bus_no="ITER-01",
            route_name="Patia to Campus",
            coordinates=[[20.1, 85.8], [20.2, 85.9]],
            waypoints=[[20.1, 85.8], [20.2, 85.9]],
            driver=self.driver1,
            is_active=True,
            live_latitude=20.15,
            live_longitude=85.85,
            location_updated_at=timezone.now(),
        )

        self.client = Client()
        self.client.force_login(self.admin)

    def test_reassignment_resets_is_active_and_gps(self):
        # Post to assign driver2 to the route
        response = self.client.post(
            f"/institute/bus/{self.route.id}/assign-driver/",
            {"driver_id": str(self.driver2.id)},
        )
        self.assertEqual(response.status_code, 302)

        # Verify coordinates are cleared and is_active is False
        self.route.refresh_from_db()
        self.assertEqual(self.route.driver, self.driver2)
        self.assertFalse(self.route.is_active)
        self.assertIsNone(self.route.live_latitude)
        self.assertIsNone(self.route.live_longitude)
        self.assertIsNone(self.route.location_updated_at)

    def test_invalid_schedule_time_format_returns_error_instead_of_500(self):
        # Post a route create with malformed time "abc"
        payload = {
            "no": "ITER-99",
            "route_name": "New Route",
            "coordinates": json.dumps([[20.1, 85.8], [20.2, 85.9]]),
            "waypoints": json.dumps([[20.1, 85.8], [20.2, 85.9]]),
            "schedules": json.dumps([{"label": "Morning Pick", "time": "abc"}]),
            "stops": json.dumps([
                {"name": "Stop A", "lat": 20.1, "lng": 85.8},
                {"name": "Stop B", "lat": 20.2, "lng": 85.9},
            ]),
        }
        response = self.client.post("/institute/route", payload)
        self.assertEqual(response.status_code, 200)  # Re-renders form due to error
        self.assertIn("Invalid departure time format", response.context["error"])

        # Post a route edit with out-of-range hour "25:12"
        edit_payload = {
            "no": "ITER-01",
            "route_name": "Patia to Campus",
            "coordinates": json.dumps([[20.1, 85.8], [20.2, 85.9]]),
            "waypoints": json.dumps([[20.1, 85.8], [20.2, 85.9]]),
            "schedules": json.dumps([{"label": "Morning Pick", "time": "25:12"}]),
            "stops": json.dumps([
                {"name": "Stop A", "lat": 20.1, "lng": 85.8},
                {"name": "Stop B", "lat": 20.2, "lng": 85.9},
            ]),
        }
        response = self.client.post(f"/institute/bus/{self.route.id}/edit/", edit_payload)
        self.assertEqual(response.status_code, 200)  # Re-renders form due to error
        self.assertIn("Invalid departure time format", response.context["error"])

    def test_institute_deletion_deletes_admin(self):
        admin_id = self.admin.id
        self.institute.delete()

        # Check that the admin user was also deleted
        self.assertFalse(User.objects.filter(id=admin_id).exists())
