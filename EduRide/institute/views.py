import json
import hmac
import hashlib

import razorpay
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from .models import Institute, Route
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_POST
from django.contrib.auth.password_validation import validate_password

# OLD: from django.contrib.auth.decorators import login_required
# NEW: We use our custom institute_required decorator instead.
# It checks BOTH that the user is logged in AND has role="institute_admin".
from student.decorators import institute_required, payment_required

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


# ---------------------------------------------------------------------------
#  Helper: get the Razorpay client (created on first use)
# ---------------------------------------------------------------------------

def _get_razorpay_client():
    """
    Create and return a Razorpay client using settings from settings.py.
    Returns None if keys are not configured.
    """
    key_id = settings.RAZORPAY_KEY_ID
    key_secret = settings.RAZORPAY_KEY_SECRET
    if not key_id or not key_secret:
        return None
    return razorpay.Client(auth=(key_id, key_secret))


# ===========================================================================
#  INSTITUTE VIEWS (all protected by @institute_required + @payment_required)
# ===========================================================================

@institute_required
@payment_required
def institute_admin(request):
    """Institute admin dashboard — shows stats, lists, and map."""
    institute = request.user.institute  # via OneToOneField
    routes = Route.objects.filter(institute=institute).select_related("driver")

    # ── Bus map data ──
    buses = []
    for r in routes:
        buses.append({
            "id": r.id,
            "bus_no": r.bus_no,
            "route": r.route_name,
            "lat": _safe_coord(r.coordinates, 0, 20.2961),
            "lng": _safe_coord(r.coordinates, 1, 85.8245),
            "routeCoords": r.coordinates if r.coordinates else [],
        })

    # ── Aggregate counts ──
    total_buses = routes.count()
    active_buses = routes.filter(is_active=True).count()
    inactive_buses = total_buses - active_buses

    # Students & drivers belonging to this institute (via UserProfile.institute FK)
    students = User.objects.filter(
        profile__role="student", profile__institute=institute
    ).select_related("profile").order_by("username")

    drivers = User.objects.filter(
        profile__role="driver", profile__institute=institute
    ).select_related("profile").order_by("username")

    total_students = students.count()
    total_drivers = drivers.count()

    # Drivers without an assigned bus
    assigned_driver_ids = routes.filter(driver__isnull=False).values_list("driver_id", flat=True)
    drivers_without_bus = drivers.exclude(id__in=assigned_driver_ids)
    drivers_without_bus_ids = set(drivers_without_bus.values_list("id", flat=True))

    # Buses without a driver
    buses_without_driver = routes.filter(driver__isnull=True)

    return render(request, "institute_admin.html", {
        "buses": buses,
        "institute": institute,
        # Counts
        "total_buses": total_buses,
        "active_buses": active_buses,
        "inactive_buses": inactive_buses,
        "total_students": total_students,
        "total_drivers": total_drivers,
        # Lists
        "students": students,
        "drivers": drivers,
        "drivers_without_bus": drivers_without_bus,
        "drivers_without_bus_ids": drivers_without_bus_ids,
        "buses_without_driver": buses_without_driver,
    })

@institute_required
@payment_required
def buslist(request):
    """List all buses, ordered by newest first."""
    institute = request.user.institute
    buses = Route.objects.filter(institute=institute).select_related("driver").order_by('-id')

    # Get drivers who are NOT already assigned to any route.
    # Only show drivers from THIS institute.
    assigned_driver_ids = Route.objects.filter(
        institute=institute, driver__isnull=False
    ).values_list("driver_id", flat=True)

    available_drivers = User.objects.filter(
        profile__role="driver",
        profile__institute=institute,
    ).exclude(id__in=assigned_driver_ids)

    return render(request, "buslist.html", {
        "buses": buses,
        "available_drivers": available_drivers,
    })


@institute_required
@payment_required
@require_POST
def assign_driver(request, bus_id):
    """Assign or unassign a driver to/from a route."""
    institute = request.user.institute
    bus = get_object_or_404(Route, id=bus_id, institute=institute)
    driver_id = request.POST.get("driver_id", "").strip()

    if driver_id == "":
        # Unassign: remove driver and deactivate the route.
        bus.driver = None
        bus.is_active = False
        bus.save(update_fields=["driver", "is_active"])
        messages.success(request, f"Driver unassigned from bus {bus.bus_no}.")
    else:
        try:
            # Only allow assigning drivers from THIS institute.
            driver_user = User.objects.get(
                id=driver_id,
                profile__role="driver",
                profile__institute=institute,
            )
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
@payment_required
def route(request):
    """Create a new bus route (form + map)."""
    institute = request.user.institute

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
            institute=institute,  # Auto-set to the logged-in admin's institute
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
@payment_required
def edit_route(request, bus_id):
    """Edit an existing bus route."""
    institute = request.user.institute
    bus = get_object_or_404(Route, id=bus_id, institute=institute)

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
@payment_required
@require_POST
def delete_route(request, bus_id):
    """Delete a bus route. Only works via POST to prevent accidental deletion."""
    institute = request.user.institute
    bus = get_object_or_404(Route, id=bus_id, institute=institute)
    bus.delete()
    return redirect("buslist")


# ===========================================================================
#  PAYMENT VIEWS
# ===========================================================================

@institute_required
def payment_page(request):
    """
    Show the payment page with Razorpay checkout.

    If the institute has already paid, redirect to the dashboard.
    Otherwise, create a Razorpay order and render the payment form.
    """
    institute = request.user.institute

    if institute.has_paid:
        return redirect("institute_admin")

    client = _get_razorpay_client()
    if client is None:
        messages.error(
            request,
            "Payment gateway is not configured. "
            "Please set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET environment variables."
        )
        return render(request, "payment.html", {"institute": institute})

    # If we already have an unpaid order, reuse it instead of creating a new one.
    if institute.razorpay_order_id:
        return render(request, "payment.html", {
            "institute": institute,
            "razorpay_order_id": institute.razorpay_order_id,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            "amount": 49900,
            "amount_display": "499",
        })

    # Create a Razorpay order (amount in paise: ₹499 = 49900 paise)
    order_data = {
        "amount": 49900,  # ₹499.00
        "currency": "INR",
        "receipt": f"edu_{institute.institute_code}",
        "notes": {
            "institute_code": institute.institute_code,
            "institute_name": institute.name,
        },
    }

    try:
        order = client.order.create(data=order_data)
    except Exception as e:
        messages.error(request, f"Could not create payment order: {e}")
        return render(request, "payment.html", {"institute": institute})

    # Save the order ID so we can verify it later.
    institute.razorpay_order_id = order["id"]
    institute.save(update_fields=["razorpay_order_id"])

    return render(request, "payment.html", {
        "institute": institute,
        "razorpay_order_id": order["id"],
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "amount": order_data["amount"],
        "amount_display": "499",
    })


@institute_required
@require_POST
def verify_payment(request):
    """
    Verify the Razorpay payment signature and mark the institute as paid.

    Razorpay sends back three values after a successful payment:
    - razorpay_order_id
    - razorpay_payment_id
    - razorpay_signature

    We verify the signature to ensure the payment is genuine.
    """
    institute = request.user.institute

    razorpay_order_id = request.POST.get("razorpay_order_id", "")
    razorpay_payment_id = request.POST.get("razorpay_payment_id", "")
    razorpay_signature = request.POST.get("razorpay_signature", "")

    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        messages.error(request, "Payment verification failed: missing data.")
        return redirect("institute_payment")

    # Verify that the order ID matches what we stored.
    if institute.razorpay_order_id != razorpay_order_id:
        messages.error(request, "Payment verification failed: order mismatch.")
        return redirect("institute_payment")

    # Verify the signature using HMAC-SHA256.
    # Razorpay uses: HMAC_SHA256(order_id + "|" + payment_id, key_secret)
    generated_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if generated_signature != razorpay_signature:
        messages.error(request, "Payment verification failed: invalid signature.")
        return redirect("institute_payment")

    # Payment verified! Mark the institute as paid.
    institute.has_paid = True
    institute.save(update_fields=["has_paid"])

    messages.success(request, "Payment successful! You can now manage buses.")
    return redirect("institute_admin")


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
    NEW: Also creates an Institute record with the admin's chosen name.
         The institute code is auto-generated.
    """
    if request.user.is_authenticated and hasattr(request.user, "profile") and request.user.profile.role == "institute_admin":
        return redirect("institute_admin")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        institute_name = request.POST.get("institute_name", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not username or not email or not password or not confirm_password or not institute_name:
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

        # --- Create the user + profile + institute atomically ---
        # WHY transaction.atomic()?
        # If any of the three creates fail, they ALL roll back.
        with transaction.atomic():
            # Create the Django User (no is_staff=True anymore!)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )

            # Create a UserProfile with role="institute_admin".
            # institute is NULL for admins — they're linked via Institute.admin.
            UserProfile.objects.create(user=user, role="institute_admin")

            # Create the Institute record.
            # institute_code is auto-generated in Institute.save().
            Institute.objects.create(
                name=institute_name,
                admin=user,
            )

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


# ===========================================================================
#  REMOVE STUDENT / DRIVER (dashboard actions)
# ===========================================================================

@institute_required
@payment_required
@require_POST
def remove_student(request, user_id):
    """Remove a student from the institute (deletes the User entirely)."""
    institute = request.user.institute
    student_user = get_object_or_404(
        User,
        id=user_id,
        profile__role="student",
        profile__institute=institute,
    )
    student_user.delete()  # cascades to UserProfile
    messages.success(request, f"Student '{student_user.username}' has been removed.")
    return redirect("institute_admin")


@institute_required
@payment_required
@require_POST
def remove_driver(request, user_id):
    """Remove a driver from the institute (deletes the User entirely).
    Also unassigns them from any route first."""
    institute = request.user.institute
    driver_user = get_object_or_404(
        User,
        id=user_id,
        profile__role="driver",
        profile__institute=institute,
    )
    # Unassign from any route before deleting (SET_NULL will handle this
    # automatically via on_delete, but let's also deactivate the route).
    if hasattr(driver_user, "assigned_route"):
        route = driver_user.assigned_route
        route.is_active = False
        route.save(update_fields=["is_active"])
    driver_user.delete()  # cascades to UserProfile; route.driver → NULL via SET_NULL
    messages.success(request, f"Driver '{driver_user.username}' has been removed.")
    return redirect("institute_admin")