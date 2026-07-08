from django.contrib import admin
from .models import UserProfile


# @admin.register(UserProfile) is a shortcut for admin.site.register(UserProfile).
# It tells Django: "Show UserProfile in the /admin/ panel."
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    This controls how UserProfile appears in the Django admin panel.

    list_display: columns shown in the list view
    list_filter:  sidebar filter to quickly filter by role
    search_fields: search box to find users by username
    """

    # Show these columns when viewing the list of all profiles.
    list_display = ("user", "role", "institute")

    # Add a sidebar filter so you can click "Student" / "Institute Admin" / "Driver"
    # to see only users with that role.
    list_filter = ("role",)

    # Allow searching by username in the admin search bar.
    # "user__username" means: follow the 'user' relation and search its 'username' field.
    search_fields = ("user__username",)
