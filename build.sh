#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r EduRide/requirements.txt

# Navigate to Django application directory
cd EduRide

# Build Tailwind CSS styles using django-tailwind (pytailwindcss wrapper)
python3 manage.py tailwind build

# Collect all static files into staticfiles/ for WhiteNoise to serve
python3 manage.py collectstatic --no-input

# Apply database migrations on the production database
python3 manage.py migrate
