import json
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from .models import Route
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_POST
from django.contrib.auth.password_validation import validate_password

# OLD: from django.contrib.auth.decorators import login_required
# NEW: We use our custom institute_required decorator instead.
# It checks BOTH that the user is logged in AND has role="institute_admin".
from student.decorators import institute_required

# Import UserProfile so we can create one during institute signup.
from student.models import UserProfile


# ---------------------------------------------------------------------------
#  Helper: safely extract coordinates
# ---------------------------------------------------------------------------

def _safe_coord(coordinates, index, default):
    """Safely extract a coordinate value, returning default on any failure."""
    try:
        return coordinates[0][index]
    except (IndexError, TypeError, KeyError):
        return default


# ===========================================================================
#  INSTITUTE VIEWS (all protected by @institute_required)
# ===========================================================================

# OLD: @login_required(login_url='institute_signin')
# PROBLEM: Any logged-in user (even a student) could access this page.
# NEW: @institute_required only allows users with UserProfile.role == "institute_admin".

@institute_required
def institute_admin(request):
    """Institute admin dashboard — shows all buses on a map."""
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
        })

    return render(request, "institute_admin.html", {
        "buses": buses,
    })

@institute_required
def buslist(request):
    """List all buses, ordered by newest first."""
    buses = Route.objects.select_related("driver").all().order_by('-id')

    # Get drivers who are NOT already assigned to any route.
    # These are the ones available in the "Assign Driver" dropdown.
    assigned_driver_ids = Route.objects.filter(driver__isnull=False).values_list("driver_id", flat=True)
    available_drivers = User.objects.filter(
        profile__role="driver"
    ).exclude(id__in=assigned_driver_ids)

    return render(request, "buslist.html", {
        "buses": buses,
        "available_drivers": available_drivers,
    })


@institute_required
@require_POST
def assign_driver(request, bus_id):
    """Assign or unassign a driver to/from a route."""
    bus = get_object_or_404(Route, id=bus_id)
    driver_id = request.POST.get("driver_id", "").strip()

    if driver_id == "":
        # Unassign: remove driver and deactivate the route.
        bus.driver = None
        bus.is_active = False
        bus.save(update_fields=["driver", "is_active"])
        messages.success(request, f"Driver unassigned from bus {bus.bus_no}.")
    else:
        try:
            driver_user = User.objects.get(id=driver_id, profile__role="driver")
        except User.DoesNotExist:
            messages.error(request, "Invalid driver selected.")
            return redirect("buslist")

        # Check the driver isn't already assigned to another route.
        if Route.objects.filter(driver=driver_user).exclude(id=bus_id).exists():
            messages.error(request, f"{driver_user.username} is already assigned to another bus.")
            return redirect("buslist")

        bus.driver = driver_user
        bus.save(update_fields=["driver"])
        messages.success(request, f"Driver {driver_user.username} assigned to bus {bus.bus_no}.")

    return redirect("buslist")

@institute_required
def route(request):
    """Create a new bus route (form + map)."""
    if request.method == "POST":
        bus_no = request.POST.get("no", "")
        route_name = request.POST.get("route_name", "")
        coordinates = request.POST.get("coordinates")
        waypoints = request.POST.get("waypoints")

        if not bus_no or not route_name:
            return render(request, "create_route.html", {
                "error": "Bus number and route name are required."
            })

        if not coordinates or not waypoints:
            return render(request, "create_route.html", {
                "error": "Please create a valid route on the map."
            })

        try:
            coordinates_data = json.loads(coordinates)
            waypoints_data = json.loads(waypoints)
        except json.JSONDecodeError:
            return render(request, "create_route.html", {
                "error": "Invalid route data."
            })

        bus = Route(
            bus_no=bus_no,
            route_name=route_name,
            coordinates=coordinates_data,
            waypoints=waypoints_data
        )

        try:
            bus.full_clean()
            bus.save()
        except ValidationError as exc:
            return render(request, "create_route.html", {
                "error": " ".join(
                    msg for msg_list in exc.message_dict.values() for msg in msg_list
                ) if hasattr(exc, 'message_dict') else " ".join(exc.messages),
                "form_data": {
                    "bus_no": bus_no,
                    "route_name": route_name,
                },
            })

        return redirect("buslist")

    return render(request, "create_route.html")


@institute_required
def edit_route(request, bus_id):
    """Edit an existing bus route."""
    bus = get_object_or_404(Route, id=bus_id)

    if request.method == "POST":
        bus_no = request.POST.get("no", "")
        route_name = request.POST.get("route_name", "")
        coordinates = request.POST.get("coordinates")
        waypoints = request.POST.get("waypoints")

        if not coordinates or not waypoints:
            return render(request, "edit_route.html", {
                "bus": bus,
                "error": "Please create a valid route before saving."
            })

        try:
            coordinates_data = json.loads(coordinates)
            waypoints_data = json.loads(waypoints)
        except json.JSONDecodeError:
            return render(request, "edit_route.html", {
                "bus": bus,
                "error": "Invalid route data."
            })

        bus.bus_no = bus_no
        bus.route_name = route_name
        bus.coordinates = coordinates_data
        bus.waypoints = waypoints_data

        try:
            bus.full_clean()
            bus.save()
        except ValidationError as exc:
            return render(request, "edit_route.html", {
                "bus": bus,
                "error": " ".join(
                    msg for msg_list in exc.message_dict.values() for msg in msg_list
                ) if hasattr(exc, 'message_dict') else " ".join(exc.messages),
            })

        return redirect("buslist")

    return render(request, "edit_route.html", {"bus": bus})


@institute_required
@require_POST
def delete_route(request, bus_id):
    """Delete a bus route. Only works via POST to prevent accidental deletion."""
    bus = get_object_or_404(Route, id=bus_id)
    bus.delete()
    return redirect("buslist")


# ===========================================================================
#  AUTHENTICATION VIEWS (no role decorator needed — these are public pages)
# ===========================================================================

def institute_signup(request):
    """
    Institute admin registration.

    CHANGES FROM OLD CODE:
    ----------------------
    OLD: user.is_staff = True  (gave access to Django admin panel — security risk!)
    NEW: UserProfile.objects.create(user=user, role="institute_admin")
         (only gives access to institute pages, NOT Django admin)
    """
    if request.user.is_authenticated and hasattr(request.user, "profile") and request.user.profile.role == "institute_admin":
        return redirect("institute_admin")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not username or not email or not password or not confirm_password:
            messages.error(request, "All fields are required.")
            return redirect("institute_signup")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("institute_signup")

        # Validate password strength using Django's AUTH_PASSWORD_VALIDATORS.
        # Without this, users can register with passwords like "1" or "password".
        try:
            validate_password(password)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return redirect("institute_signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("institute_signup")

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("institute_signup")

        # --- Create the user + profile atomically ---
        # WHY transaction.atomic()?
        # If UserProfile.objects.create() fails after the User is created,
        # the User is rolled back too. Without this, the user would be
        # "orphaned": they can't log in (no profile) and can't re-register
        # (username/email already taken).
        with transaction.atomic():
            # Create the Django User (no is_staff=True anymore!)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )

            # Create a UserProfile with role="institute_admin".
            # This is how our @institute_required decorator knows this user is an admin.
            UserProfile.objects.create(user=user, role="institute_admin")

        messages.success(request, "Institute admin account created successfully.")
        return redirect("institute_signin")

    return render(request, "institute_reg/signup.html")


def institute_signin(request):
    """Institute admin login page."""
    # Only redirect if user is logged in AND has institute_admin role.
    # Without the role check, a student visiting this page would redirect
    # to institute_admin, which requires institute role → redirects back here → loop!
    if request.user.is_authenticated and hasattr(request.user, "profile") and request.user.profile.role == "institute_admin":
        return redirect("institute_admin")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Verify this user actually has the "institute_admin" role before logging in.
            # Without this check, a student could log in here and get
            # stuck in a redirect loop.
            if not hasattr(user, "profile") or user.profile.role != "institute_admin":
                messages.error(request, "This account is not an institute admin account.")
                return redirect("institute_signin")

            login(request, user)
            return redirect("institute_admin")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "institute_reg/signin.html")


# @require_POST blocks GET requests (prevents <img src="/logout/"> attacks).
# CSRF protection is intentionally kept — the token in the logout form is valid.
@require_POST
def institute_logout(request):
    """Log out and redirect to the institute login page."""
    logout(request)
    return redirect("institute_signin")