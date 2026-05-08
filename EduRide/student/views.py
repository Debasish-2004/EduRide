from django.shortcuts import render, redirect
from django.db import transaction
from django.http import JsonResponse
from institute.models import Route
from django.views.decorators.http import require_POST
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

# OLD: from django.contrib.auth.decorators import login_required
# NEW: We use our custom student_required decorator instead.
# It checks BOTH that the user is logged in AND has role="student".
from .decorators import student_required

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User

# Import UserProfile so we can create one during signup.
from .models import UserProfile


def _safe_coord(coordinates, index, default):
    """Safely extract a coordinate value, returning default on any failure."""
    try:
        return coordinates[0][index]
    except (IndexError, TypeError, KeyError):
        return default


# ---------------------------------------------------------------------------
#  Student Home (protected by @student_required)
# ---------------------------------------------------------------------------

# OLD: @login_required(login_url='student_signin')
# PROBLEM: Any logged-in user (even an institute admin) could access this page.
# NEW: @student_required only allows users with UserProfile.role == "student".
@student_required
def home(request):
    routes = Route.objects.all()

    buses = []
    for route in routes:
        buses.append({
            "id": route.id,
            "bus_no": route.bus_no,
            "route": route.route_name,
            "lat": _safe_coord(route.coordinates, 0, 20.2961),
            "lng": _safe_coord(route.coordinates, 1, 85.8245),
            "routeCoords": route.coordinates if route.coordinates else [],
            "is_active": route.is_active,
        })

    return render(request, "index.html", {
        "buses": buses,
    })


# ---------------------------------------------------------------------------
#  Bus Locations API (polled by the student's browser every ~5 seconds)
# ---------------------------------------------------------------------------

@student_required
def bus_locations_api(request):
    """
    Returns JSON with all buses and their current live positions.
    The student's JavaScript polls this endpoint to update map markers.
    """
    routes = Route.objects.all()

    buses = []
    for route in routes:
        # Use live GPS position if available, otherwise fall back to
        # the first point of the static route coordinates.
        if route.live_latitude is not None and route.live_longitude is not None:
            lat = route.live_latitude
            lng = route.live_longitude
        else:
            lat = _safe_coord(route.coordinates, 0, 20.2961)
            lng = _safe_coord(route.coordinates, 1, 85.8245)

        buses.append({
            "id": route.id,
            "bus_no": route.bus_no,
            "route": route.route_name,
            "lat": lat,
            "lng": lng,
            "is_active": route.is_active,
            "last_updated": route.location_updated_at.isoformat() if route.location_updated_at else None,
        })

    return JsonResponse(buses, safe=False)


# ---------------------------------------------------------------------------
#  Student Sign In (no decorator needed — this is the login page itself!)
# ---------------------------------------------------------------------------

def student_signin(request):
    # If the user is already logged in AND has the student role,
    # redirect to home instead of showing the login form again.
    # WHY the extra check? Without it, a logged-in institute admin visiting
    # this page would be redirected to "home", which requires student role,
    # which redirects back here → infinite loop!
    if request.user.is_authenticated and hasattr(request.user, "profile") and request.user.profile.role == "student":
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # authenticate() checks if the username/password combo is correct.
        # Returns the User object if valid, or None if invalid.
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Verify this user actually has the "student" role before logging in.
            # Without this check, an institute admin could log in here and get
            # stuck in a redirect loop (home requires student role → back to signin).
            if not hasattr(user, "profile") or user.profile.role != "student":
                messages.error(request, "This account is not a student account.")
                return redirect("student_signin")

            # login() creates a session cookie so the user stays logged in.
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "student_reg/signin.html")


# ---------------------------------------------------------------------------
#  Student Sign Up (creates User + UserProfile)
# ---------------------------------------------------------------------------

def student_signup(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        # --- Validation checks ---

        # Check that no fields are empty.
        if not username or not email or not password1 or not password2:
            messages.error(request, "All fields are required.")
            return redirect("student_signup")

        # Password confirmation check.
        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect("student_signup")

        # Validate password strength using Django's AUTH_PASSWORD_VALIDATORS.
        # Without this, users can register with passwords like "1" or "password".
        try:
            validate_password(password1)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return redirect("student_signup")

        # Check if username is already taken.
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken")
            return redirect("student_signup")

        # Check if email is already registered.
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("student_signup")

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
                password=password1
            )

            # Create a UserProfile with role="student".
            # This is how Django knows this user is a student.
            # Without this, the user would not have a profile, and
            # @student_required would block them.
            UserProfile.objects.create(user=user, role="student")

        messages.success(request, "Account created successfully! Please login.")
        return redirect("student_signin")

    return render(request, "student_reg/signup.html")


# @require_POST blocks GET requests (prevents <img src="/logout/"> attacks).
# CSRF protection is intentionally kept — the token in the logout form is valid.
@require_POST
def student_logout(request):
    # logout() clears the session, making the user "not logged in" anymore.
    logout(request)
    return redirect("student_signin")