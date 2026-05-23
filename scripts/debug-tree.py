#!/usr/bin/env python
"""Debug tree building"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dispatcharr.settings')

import django
django.setup()

sys.path.insert(0, '/data/plugins/vodfs/plugin')
from tree import VirtualTree, DirectoryNode

tree = VirtualTree()
tree.build()

# Check root
root = tree.root
print(f'Root name: {root.name}')
print(f'Root children (list): {[c.name for c in root.children]}')

# Check Movies
movies = root.find_child('Movies')
if movies:
    print(f'\nMovies children: {[c.name for c in movies.children]}')
    all_movies = movies.find_child('All')
    if all_movies:
        print(f'Movies/All children count: {len(all_movies.children)}')
        for child in list(all_movies.children)[:5]:
            print(f'  - {child.name}')
    else:
        print('Movies/All not found')
else:
    print('Movies not found')

# Check integration layer
from integration import DispatcharrIntegrator
integrator = DispatcharrIntegrator()
movies_list = integrator.get_all_movies()
series_list = integrator.get_all_series()
print(f'\nIntegrator movies: {len(movies_list)}')
print(f'Integrator series: {len(series_list)}')

if movies_list:
    m = movies_list[0]
    print(f'\nFirst movie: {m.name} (id={m.id})')
    print(f'  Categories: {m.categories if hasattr(m, "categories") else "N/A"}')
