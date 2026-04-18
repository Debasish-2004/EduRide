from django.shortcuts import render, redirect
from institute.models import Route
import json
from django.contrib.auth import authenticate,login,logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required



@login_required(login_url='student_signin')
def home(request):
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

    return render(request, "index.html", {
        "buses":buses,
    })

def student_signin(request):
    if request.user.is_authenticated:
        return redirect("home")   

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("home")  
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "student_reg/signin.html")


def student_signup(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        # Password check
        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect("student_signup")

        # Username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken")
            return redirect("student_signup")

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1
        )

        messages.success(request, "Account created successfully! Please login.")
        return redirect("student_signin")

    return render(request, "student_reg/signup.html")



def student_logout(request):
    logout(request)
    return redirect("student_signin")   # where you want to go after logout