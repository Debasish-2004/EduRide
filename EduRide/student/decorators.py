"""
Role-based access control decorators for EduRide.

WHAT ARE DECORATORS?
--------------------
A decorator is a function that wraps another function to add extra behavior.
In Django, decorators are used to add checks BEFORE a view runs.

Example:
    @student_required
    def home(request):
        ...

This is equivalent to:
    def home(request):
        ...
    home = student_required(home)

When someone visits the 'home' URL, Django first runs the student_required check.
If the check passes, the actual home() view runs.
If it fails, the user is redirected to a login page.

HOW THESE DECORATORS WORK:
--------------------------
1. Check if user is logged in (authenticated).
2. Check if user has a UserProfile (they should, if they signed up properly).
3. Check if the profile's role matches the required role.
4. If any check fails, redirect to the appropriate login page.

WHY NOT JUST USE @login_required?
----------------------------------
@login_required only checks: "Is the user logged in?"
It does NOT check: "Is the user a STUDENT?" or "Is the user an INSTITUTE ADMIN?"
So a student who knows the URL /institute/buslist could access it.
Our decorators fix that.
"""

from functools import wraps  # wraps preserves the original function's name/docstring

from django.shortcuts import redirect


# ---------------------------------------------------------------------------
#  Helper: generic role checker (used by all role-specific decorators below)
# ---------------------------------------------------------------------------

def _role_required(required_role, login_url):
    """
    Factory function that creates a role-checking decorator.

    Parameters:
        required_role (str): The role string to match, e.g. "student" or "institute_admin".
        login_url (str): The URL name to redirect to if the check fails.

    Returns:
        A decorator function.

    HOW THIS FACTORY PATTERN WORKS:
    --------------------------------
    Instead of writing 3 nearly-identical decorators, we write ONE generic function
    that CREATES a decorator for any role. This avoids copy-pasting the same logic.

    _role_required("student", "student_signin")  -->  returns a decorator for students
    _role_required("institute_admin", "institute_signin")  -->  returns one for admins
    """

    def decorator(view_func):
        @wraps(view_func)  # keeps the original function's __name__ and __doc__
        def wrapper(request, *args, **kwargs):

            # STEP 1: Is the user logged in?
            if not request.user.is_authenticated:
                # Not logged in → send to the appropriate login page.
                return redirect(login_url)

            # STEP 2: Does the user have a UserProfile?
            # We use hasattr() to safely check. If the user was created before
            # we added UserProfile (e.g., old accounts, superusers created via
            # 'createsuperuser'), they won't have a profile yet.
            if not hasattr(request.user, "profile"):
                # No profile → we can't determine their role → redirect to login.
                return redirect(login_url)

            # STEP 3: Does the user's role match the required role?
            if request.user.profile.role != required_role:
                # Wrong role → redirect to login page.
                # For example, an institute admin trying to access student pages.
                return redirect(login_url)

            # All checks passed! Run the actual view function.
            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
#  Role-specific decorators (these are what you use in views.py)
# ---------------------------------------------------------------------------

def student_required(view_func):
    """
    Only allows users with role="student" to access the view.
    Everyone else is redirected to the student login page.

    Usage:
        @student_required
        def home(request):
            ...
    """
    return _role_required("student", "student_signin")(view_func)


def institute_required(view_func):
    """
    Only allows users with role="institute_admin" to access the view.
    Everyone else is redirected to the institute login page.

    Usage:
        @institute_required
        def institute_admin(request):
            ...
    """
    return _role_required("institute_admin", "institute_signin")(view_func)


def payment_required(view_func):
    """
    Decorator for institute views that require the institute to have paid.

    MUST be used AFTER @institute_required, like this:
        @institute_required
        @payment_required
        def buslist(request):
            ...

    This ensures:
    1. User is logged in and is an institute_admin (checked by @institute_required).
    2. The institute has completed payment (checked by this decorator).

    If the institute has NOT paid, the user is redirected to the payment page.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # At this point, @institute_required has already verified the user
        # is an authenticated institute_admin.  We just need to check payment.
        institute = request.user.institute  # via Institute.admin OneToOneField
        if not institute.has_paid:
            return redirect("institute_payment")

        return view_func(request, *args, **kwargs)

    return wrapper


def driver_required(view_func):
    """
    Only allows users with role="driver" to access the view.
    Everyone else is redirected to a login page.

    NOTE: There are no driver views yet, but this decorator is ready
    for when you create them.

    Usage:
        @driver_required
        def driver_dashboard(request):
            ...
    """
    return _role_required("driver", "driver_signin")(view_func)


def super_admin_required(view_func):
    """
    Only allows Django superusers (is_superuser=True) to access the view.

    This is separate from UserProfile.role because super admin is a
    Django-level privilege, not a role in our app.

    Superusers are created via: python manage.py createsuperuser

    Usage:
        @super_admin_required
        def admin_dashboard(request):
            ...
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        # Check if logged in
        if not request.user.is_authenticated:
            return redirect("student_signin")

        # Check if the user is a Django superuser
        if not request.user.is_superuser:
            return redirect("student_signin")

        # Superuser confirmed → run the view
        return view_func(request, *args, **kwargs)

    return wrapper
