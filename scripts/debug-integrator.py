#!/usr/bin/env python
"""Debug integrator"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dispatcharr.settings')

import django
django.setup()

sys.path.insert(0, '/data/plugins/vodfs/plugin')

# Check imports
try:
    from apps.vod.models import Movie, Series
    print(f'Movie model: {Movie}')
    print(f'Series model: {Series}')
    
    # Count directly
    movie_count = Movie.objects.count()
    series_count = Series.objects.count()
    print(f'\nDirect Movie count: {movie_count}')
    print(f'Direct Series count: {series_count}')
    
    # Try with select_related
    movies = Movie.objects.all().select_related('logo')
    print(f'Movie queryset count: {movies.count()}')
    
    # Check first movie
    if movie_count > 0:
        m = Movie.objects.first()
        print(f'\nFirst movie: name={m.name}, year={m.year}')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
