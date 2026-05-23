#!/usr/bin/env python
"""Debug integrator import"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dispatcharr.settings')

import django
django.setup()

sys.path.insert(0, '/data/plugins/vodfs/plugin')

# Check integration module
from integration import DispatcharrIntegrator, DJANGO_AVAILABLE, Movie

print(f'DJANGO_AVAILABLE: {DJANGO_AVAILABLE}')
print(f'Movie from integration: {Movie}')

integrator = DispatcharrIntegrator()
print(f'Integrator available: {integrator.is_available()}')

movies = integrator.get_all_movies()
print(f'Integrator movies: {len(movies)}')

series = integrator.get_all_series()
print(f'Integrator series: {len(series)}')
