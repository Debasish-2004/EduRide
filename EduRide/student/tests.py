from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from institute.models import Institute, Route
from student.models import UserProfile


class OfflineBusGPSTests(TestCase):
    def setUp(self):
        # Create an Admin and an Institute
        self.admin_user = User.objects.create_user(username="instadmin", password="password123")
        self.institute = Institute.objects.create(name="Test Institute", admin=self.admin_user, has_paid=True)
        # Link admin user profile (normally not strictly required for some actions, but good to have)
        UserProfile.objects.create(
            user=self.admin_user,
            role="institute_admin",
            institute=self.institute,
        )

        # Create a Driver user
        self.driver_user = User.objects.create_user(username="busdriver", password="password123")
        UserProfile.objects.create(user=self.driver_user, role="driver", institute=self.institute)

        # Create a Student user
        self.student_user = User.objects.create_user(username="student1", password="password123")
        self.student_profile = UserProfile.objects.create(
            user=self.student_user, role="student", institute=self.institute
        )

        # Create a Route
        self.route = Route.objects.create(
            institute=self.institute,
            bus_no="BUS-100",
            route_name="Route 100",
            coordinates=[[20.2961, 85.8245], [20.3000, 85.8300]],
            waypoints=[[20.2961, 85.8245], [20.3000, 85.8300]],
            driver=self.driver_user,
        )

        self.client = Client()

    def test_student_api_gates_on_is_active(self):
        # Set some live coordinates on the route
        self.route.live_latitude = 22.2222
        self.route.live_longitude = 88.8888
        self.route.location_updated_at = timezone.now()
        self.route.is_active = False
        self.route.save()

        # Log in as student
        self.client.force_login(self.student_user)

        # Fetch bus locations API
        response = self.client.get("/student/api/bus-locations/")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Route is inactive: should fall back to first coordinate of static route [20.2961, 85.8245]
        bus_data = data[0]
        self.assertAlmostEqual(bus_data["lat"], 20.2961)
        self.assertAlmostEqual(bus_data["lng"], 85.8245)

        # Activate the route
        self.route.is_active = True
        self.route.save()

        response = self.client.get("/student/api/bus-locations/")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Route is active: should return the live coordinates
        bus_data = data[0]
        self.assertAlmostEqual(bus_data["lat"], 22.2222)
        self.assertAlmostEqual(bus_data["lng"], 88.8888)

    def test_driver_unassignment_clears_gps(self):
        # Set live coordinates on the route
        self.route.live_latitude = 22.2222
        self.route.live_longitude = 88.8888
        self.route.location_updated_at = timezone.now()
        self.route.is_active = True
        self.route.save()

        # Log in as institute admin
        self.client.force_login(self.admin_user)

        # Unassign the driver
        response = self.client.post(f"/institute/bus/{self.route.id}/assign-driver/", {"driver_id": ""})
        self.assertEqual(response.status_code, 302)  # Redirects back to buslist

        # Refresh route from DB
        self.route.refresh_from_db()

        # Verify driver is unassigned, route is inactive, and GPS is cleared
        self.assertIsNone(self.route.driver)
        self.assertFalse(self.route.is_active)
        self.assertIsNone(self.route.live_latitude)
        self.assertIsNone(self.route.live_longitude)
        self.assertIsNone(self.route.location_updated_at)

    def test_driver_removal_clears_gps(self):
        # Set live coordinates on the route
        self.route.live_latitude = 22.2222
        self.route.live_longitude = 88.8888
        self.route.location_updated_at = timezone.now()
        self.route.is_active = True
        self.route.save()

        # Log in as institute admin
        self.client.force_login(self.admin_user)

        # Remove the driver
        response = self.client.post(f"/institute/driver/{self.driver_user.id}/remove/")
        self.assertEqual(response.status_code, 302)  # Redirects to admin dashboard

        # Refresh route from DB
        self.route.refresh_from_db()

        # Verify route is inactive, driver is NULL, and GPS is cleared
        self.assertIsNone(self.route.driver)
        self.assertFalse(self.route.is_active)
        self.assertIsNone(self.route.live_latitude)
        self.assertIsNone(self.route.live_longitude)
        self.assertIsNone(self.route.location_updated_at)
