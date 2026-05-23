#!/usr/bin/env python
"""Quick setup script for Dispatcharr integration testing

Reads credentials from environment variables or .env.secrets file.
Never hardcodes credentials in this file.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dispatcharr.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from apps.vod.models import M3UAccount

User = get_user_model()

# Read credentials from environment
ADMIN_USERNAME = os.environ.get('DISPATCHARR_ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('DISPATCHARR_ADMIN_PASSWORD', '')
MEGA_URL = os.environ.get('MEGA_SERVER', '')
MEGA_USERNAME = os.environ.get('MEGA_USERNAME', '')
MEGA_PASSWORD = os.environ.get('MEGA_PASSWORD', '')
STRONG_URL = os.environ.get('STRONG_SERVER', '')
STRONG_USERNAME = os.environ.get('STRONG_USERNAME', '')
STRONG_PASSWORD = os.environ.get('STRONG_PASSWORD', '')

# Create admin user if not exists
if ADMIN_PASSWORD:
    if not User.objects.filter(username=ADMIN_USERNAME).exists():
        User.objects.create_superuser(ADMIN_USERNAME, 'admin@localhost', ADMIN_PASSWORD)
        print(f"Created admin user: {ADMIN_USERNAME}")
    else:
        print(f"Admin user exists: {ADMIN_USERNAME}")
else:
    print("Warning: DISPATCHARR_ADMIN_PASSWORD not set, skipping admin user creation")

# Get token
user = User.objects.filter(username=ADMIN_USERNAME).first()
if user:
    token, _ = Token.objects.get_or_create(user=user)
    print(f"TOKEN={token.key}")

# Check existing accounts
accounts = M3UAccount.objects.all()
print(f"Existing accounts: {list(accounts.values_list('name', flat=True))}")

# Add MEGA account if not exists
if MEGA_URL and MEGA_USERNAME and MEGA_PASSWORD:
    if not M3UAccount.objects.filter(name='MEGA').exists():
        M3UAccount.objects.create(
            name='MEGA',
            url=MEGA_URL,
            username=MEGA_USERNAME,
            password=MEGA_PASSWORD
        )
        print("Added MEGA account")
    else:
        print("MEGA account already exists")
else:
    print("Warning: MEGA credentials not set, skipping MEGA account creation")

# Add STRONG account if not exists
if STRONG_URL and STRONG_USERNAME and STRONG_PASSWORD:
    if not M3UAccount.objects.filter(name='STRONG').exists():
        M3UAccount.objects.create(
            name='STRONG',
            url=STRONG_URL,
            username=STRONG_USERNAME,
            password=STRONG_PASSWORD
        )
        print("Added STRONG account")
    else:
        print("STRONG account already exists")
else:
    print("Warning: STRONG credentials not set, skipping STRONG account creation")

print("Setup complete")
