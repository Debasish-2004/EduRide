from django.shortcuts import render

# Create your views here.
def institute_admin(request):
    return render(request, "institute_admin.html")

def buslist(request):
    return render(request, "buslist.html")

def route(request):
    return render(request, "create_route.html")