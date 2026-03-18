from django.contrib import admin
from django.urls import include, path
from . import views

urlpatterns = [
    path('', views.institute_admin, name='institute_admin'),
    path('buslist', views.buslist, name='buslist'),
    path('route', views.route, name='route'),
    path("bus/<int:bus_id>/edit/", views.edit_route, name="edit_route"),
    path("bus/<int:bus_id>/delete/", views.delete_route, name="delete_route"),
]