from django.contrib import admin
from .models import Institute, Route
# Register your models here.

@admin.register(Institute)
class InstituteAdmin(admin.ModelAdmin):
    list_display = ("name", "institute_code", "admin", "has_paid", "created_at")
    list_filter = ("has_paid",)
    search_fields = ("name", "institute_code", "admin__username")
    readonly_fields = ("institute_code", "created_at")

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("id", "bus_no", "route_name", "institute", "driver", "is_active")
    list_filter = ("is_active", "institute")