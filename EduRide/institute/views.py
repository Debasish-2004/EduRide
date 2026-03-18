import json
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect,get_object_or_404
from .models import Route

# Create your views here.

def institute_admin(request):
    return render(request, "institute_admin.html")


def buslist(request):
    buses = Route.objects.all().order_by('-id')
    return render(request, "buslist.html", {
        "buses": buses
    })

# the route added and then the page will forward to the buslist when added..
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
def delete_route(request, bus_id):
    bus = get_object_or_404(Route, id=bus_id)

    if request.method == "POST":
        bus.delete()

    return redirect("buslist")
