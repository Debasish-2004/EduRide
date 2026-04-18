from django.urls import include, path
from . import views
urlpatterns = [
    path('',views.home , name = 'home'),
    path("student_reg/signin/", views.student_signin, name="student_signin"),
    path("student_reg/signup/", views.student_signup, name="student_signup"),
    path("logout/", views.student_logout, name="student_logout"),
]
