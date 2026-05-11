from django.db import models

# We import Django's built-in User model so we can link our profile to it.
# Every Django project already has a User model with username, password, email, etc.
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """
    UserProfile extends Django's built-in User model with a 'role' field.

    WHY do we need this?
    --------------------
    Django's User model only has: username, password, email, is_staff, is_superuser.
    It does NOT have a 'role' field. We need roles (student, institute_admin, driver)
    to control WHO can access WHICH pages.

    HOW does it work?
    -----------------
    - Each User gets exactly ONE UserProfile (OneToOneField).
    - We check request.user.profile.role to decide what pages a user can see.
    - Super admins are detected via user.is_superuser (Django built-in), NOT via this role.

    EXAMPLE usage in views:
        if request.user.profile.role == "student":
            # allow access to student pages
    """

    # These are the allowed values for the 'role' field.
    # The first element in each tuple is stored in the database.
    # The second element is the human-readable label shown in Django admin.
    ROLE_CHOICES = [
        ("student", "Student"),
        ("institute_admin", "Institute Admin"),
        ("driver", "Driver"),
    ]

    # OneToOneField means: each User has exactly ONE UserProfile, and vice versa.
    # on_delete=CASCADE means: if the User is deleted, delete the profile too.
    # related_name="profile" means: you can do user.profile to get the UserProfile.
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    # CharField with choices restricts the value to one of the ROLE_CHOICES above.
    # default="student" means new profiles are students unless we specify otherwise.
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="student",
    )

    # Which institute this user belongs to.
    # - For institute_admin: linked via Institute.admin (OneToOneField), NOT here.
    #   This field is NULL for institute admins.
    # - For students and drivers: this is REQUIRED.
    #   They provide an institute code during signup, and we look up the Institute.
    institute = models.ForeignKey(
        "institute.Institute",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="members",
    )

    def __str__(self):
        # This controls what is displayed in Django admin and the shell.
        # Example output: "john_doe (student)"
        return f"{self.user.username} ({self.role})"
