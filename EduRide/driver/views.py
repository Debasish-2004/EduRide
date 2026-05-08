import json

from django.shortcuts import render, redirect
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from student.decorators import driver_required

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User

from student.models import UserProfile
from institute.models import Route


# ---------------------------------------------------------------------------
#  Driver Dashboard (protected by @driver_required)
# ---------------------------------------------------------------------------

@driver_required
def driver_dashboard(request):
    """Driver dashboard — shows assigned route and trip controls."""
    # Try to find the route assigned to this driver.
    # hasattr check handles the case where the driver has no assigned route.
    route = None
    if hasattr(request.user, "assigned_route"):
        route = request.user.assigned_route

    return render(request, "driver/dashboard.html", {
        "route": route,
    })


# ---------------------------------------------------------------------------
#  Toggle Trip (Start / End)
# ---------------------------------------------------------------------------

@driver_required
@require_POST
def toggle_trip(request):
    """Toggle the driver's assigned route between active and inactive."""
    if not hasattr(request.user, "assigned_route"):
        messages.error(request, "You don't have a route assigned.")
        return redirect("driver_dashboard")

    route = request.user.assigned_route
    route.is_active = not route.is_active

    # When ending a trip, clear the live GPS location so students
    # don't see a stale last-known position for an offline bus.
    if not route.is_active:
        route.live_latitude = None
        route.live_longitude = None
        route.location_updated_at = None
        route.save(update_fields=["is_active", "live_latitude", "live_longitude", "location_updated_at"])
    else:
        route.save(update_fields=["is_active"])

    status = "started" if route.is_active else "ended"
    messages.success(request, f"Trip {status} for bus {route.bus_no}.")
    return redirect("driver_dashboard")


# ---------------------------------------------------------------------------
#  Update Live Location (called by the driver's browser every ~5 seconds)
# ---------------------------------------------------------------------------

@driver_required
@require_POST
def update_location(request):
    """
    Receive the driver's GPS coordinates from their browser.

    Expects a JSON body: {"latitude": 20.296, "longitude": 85.824}
    Returns JSON: {"status": "ok"} or {"status": "error", "message": "..."}
    """
    if not hasattr(request.user, "assigned_route"):
        return JsonResponse({"status": "error", "message": "No route assigned."}, status=400)

    route = request.user.assigned_route

    if not route.is_active:
        return JsonResponse({"status": "error", "message": "Trip is not active."}, status=400)

    try:
        data = json.loads(request.body)
        lat = float(data["latitude"])
        lng = float(data["longitude"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return JsonResponse({"status": "error", "message": "Invalid data."}, status=400)

    # Basic sanity check on coordinate range.
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return JsonResponse({"status": "error", "message": "Coordinates out of range."}, status=400)

    route.live_latitude = lat
    route.live_longitude = lng
    route.location_updated_at = timezone.now()
    route.save(update_fields=["live_latitude", "live_longitude", "location_updated_at"])

    return JsonResponse({"status": "ok"})

# ---------------------------------------------------------------------------
#  Driver Sign In
# ---------------------------------------------------------------------------

def driver_signin(request):
    # If the user is already logged in AND has the driver role,
    # redirect to dashboard instead of showing the login form again.
    if (
        request.user.is_authenticated
        and hasattr(request.user, "profile")
        and request.user.profile.role == "driver"
    ):
        return redirect("driver_dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Verify this user actually has the "driver" role before logging in.
            if not hasattr(user, "profile") or user.profile.role != "driver":
                messages.error(request, "This account is not a driver account.")
                return redirect("driver_signin")

            login(request, user)
            return redirect("driver_dashboard")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "driver_reg/signin.html")


# ---------------------------------------------------------------------------
#  Driver Sign Up (creates User + UserProfile with role="driver")
# ---------------------------------------------------------------------------

def driver_signup(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        # --- Validation checks ---

        if not username or not email or not password1 or not password2:
            messages.error(request, "All fields are required.")
            return redirect("driver_signup")

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect("driver_signup")

        # Validate password strength using Django's AUTH_PASSWORD_VALIDATORS.
        try:
            validate_password(password1)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return redirect("driver_signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken")
            return redirect("driver_signup")

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("driver_signup")

        # --- Create the user + profile atomically ---
        # WHY transaction.atomic()?
        # If UserProfile.objects.create() fails after the User is created,
        # the User is rolled back too. Without this, the user would be
        # "orphaned": they can't log in (no profile) and can't re-register
        # (username/email already taken).
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
            )

            # Create a UserProfile with role="driver".
            UserProfile.objects.create(user=user, role="driver")

        messages.success(request, "Driver account created successfully! Please login.")
        return redirect("driver_signin")

    return render(request, "driver_reg/signup.html")


# ---------------------------------------------------------------------------
#  Driver Logout
# ---------------------------------------------------------------------------

# @require_POST blocks GET requests (prevents <img src="/logout/"> attacks).
# CSRF protection is intentionally kept — the token in the logout form is valid.
@require_POST
def driver_logout(request):
    logout(request)
    return redirect("driver_signin")
