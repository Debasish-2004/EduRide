from django.contrib import admin
from django.urls import include, path
from . import views

urlpatterns = [
    path('', views.institute_admin, name='institute_admin'),
    path('buslist', views.buslist, name='buslist'),
    path('route', views.route, name='route'),
    path("bus/<int:bus_id>/edit/", views.edit_route, name="edit_route"),
    path("bus/<int:bus_id>/delete/", views.delete_route, name="delete_route"),
    path("bus/<int:bus_id>/assign-driver/", views.assign_driver, name="assign_driver"),
    path("student/<int:user_id>/remove/", views.remove_student, name="remove_student"),
    path("driver/<int:user_id>/remove/", views.remove_driver, name="remove_driver"),
    path("payment/", views.payment_page, name="institute_payment"),
    path("payment/verify/", views.verify_payment, name="verify_payment"),
    path("institute_reg/signin/", views.institute_signin, name="institute_signin"),
    path("institute_reg/signup/", views.institute_signup, name="institute_signup"),
    path("logout/", views.institute_logout, name="institute_logout"),
]