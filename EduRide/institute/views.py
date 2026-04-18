import json
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect,get_object_or_404
from .models import Route
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login,logout

# Create your views here.

@login_required(login_url='institute_signin')
def institute_admin(request):
    routes = Route.objects.all()

    buses = []
    for route in routes:
        buses.append({
            "id": route.id,
            "bus_no": route.bus_no,
            "route": route.route_name,
            "lat": route.coordinates[0][0] if route.coordinates else 20.2961,
            "lng": route.coordinates[0][1] if route.coordinates else 85.8245,
            "routeCoords": route.coordinates if route.coordinates else [],
        })

    return render(request, "institute_admin.html", {
        "buses":buses,
    })

@login_required(login_url='institute_signin')
def buslist(request):
    buses = Route.objects.all().order_by('-id')
    return render(request, "buslist.html", {
        "buses": buses
    })

# the route added and then the page will forward to the buslist when added..
@login_required(login_url='institute_signin')
def route(request):
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
                "error": " ".join(exc.messages),
                "form_data": {
                    "bus_no": bus_no,
                    "route_name": route_name,
                },
            })

        return redirect("buslist")   # or any page you want after saving

    return render(request, "create_route.html")

#for edit_route.html
@login_required(login_url='institute_signin')
def edit_route(request, bus_id):
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
                "error": " ".join(exc.messages),
            })

        return redirect("buslist")

    return render(request, "edit_route.html", {"bus": bus})

#to delete bus ..
@login_required(login_url='institute_signin')
def delete_route(request, bus_id):
    bus = get_object_or_404(Route, id=bus_id)

    if request.method == "POST":
        bus.delete()

    return redirect("buslist")

#to authenticate..signup

def institute_signup(request):
    if request.user.is_authenticated:
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

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("institute_signup")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("institute_signup")

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )
        user.is_staff = True
        user.save()

        messages.success(request, "Institute admin account created successfully.")
        return redirect("institute_signin")

    return render(request, "institute_reg/signup.html")


#for signin
def institute_signin(request):
    if request.user.is_authenticated:
        return redirect("institute_admin")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("institute_admin")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "institute_reg/signin.html")

def institute_logout(request):
    logout(request)
    return redirect("institute_signin") 