from django.urls import path
from . import views

urlpatterns = [
    path("", views.driver_dashboard, name="driver_dashboard"),
    path("toggle-trip/", views.toggle_trip, name="toggle_trip"),
    path("update-location/", views.update_location, name="update_location"),
    path("driver_reg/signin/", views.driver_signin, name="driver_signin"),
    path("driver_reg/signup/", views.driver_signup, name="driver_signup"),
    path("logout/", views.driver_logout, name="driver_logout"),
]
