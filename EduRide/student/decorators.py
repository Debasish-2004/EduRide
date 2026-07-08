"""
WHY NOT JUST USE @login_required?
----------------------------------
@login_required only checks: "Is the user logged in?"
It does NOT check: "Is the user a STUDENT?" or "Is the user an INSTITUTE ADMIN?"
So a student who knows the URL /institute/buslist could access it.
Our decorators fix that.
"""
 # wraps preserves the original function's name/docstring
from functools import wraps 
from django.shortcuts import redirect


def _role_required(required_role, login_url):

    def decorator(view_func):
        @wraps(view_func) 
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return redirect(login_url)

            if not hasattr(request.user, "profile"):
                return redirect(login_url)

            if request.user.profile.role != required_role:
                return redirect(login_url)

            # All checks passed! Run the actual view function.
            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def student_required(view_func):

   # Only allows users with role="student" to access the view.
    return _role_required("student", "student_signin")(view_func)


def institute_required(view_func):
  
    ##Only allows users with role="institute_admin" to access the view.
    return _role_required("institute_admin", "institute_signin")(view_func)


def payment_required(view_func):
    """
    Decorator for institute views that require the institute to have paid.
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

    #Only allows users with role="driver" to access the view.
    return _role_required("driver", "driver_signin")(view_func)


def super_admin_required(view_func):

    #Only allows Django superusers (is_superuser=True) to access the view.\
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
