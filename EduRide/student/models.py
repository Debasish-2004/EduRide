from django.db import models
# We import Django's built-in User model so we can link our profile to it.

from django.contrib.auth.models import User
# Every Django project already has a User model with username, password, email, etc.


class UserProfile(models.Model):
    #UserProfile extends Django's built-in User model with a 'role' field.
    ROLE_CHOICES = [
        ("student", "Student"),
        ("institute_admin", "Institute Admin"),
        ("driver", "Driver"),
    ]

    # OneToOneField means: each User has exactly ONE UserProfile, and vice versa.
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )  # on_delete=CASCADE means: if the User is deleted, delete the profile too.

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="student",
    )

    institute = models.ForeignKey(
        "institute.Institute",# have not imported like user .. 
        #so it is saying that import Institute model form the institute app.
        on_delete=models.CASCADE,
        related_name="members",
    )

    def __str__(self):
        # This controls what is displayed in Django admin and the shell.
        # Example output: "john_doe (student)"
        return f"{self.user.username} ({self.role})"
