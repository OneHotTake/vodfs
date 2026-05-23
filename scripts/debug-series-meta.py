#!/usr/bin/env python
"""Debug series metadata"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dispatcharr.settings')

import django
django.setup()

sys.path.insert(0, '/data/plugins/vodfs/plugin')
from tree import VirtualTree

tree = VirtualTree()
tree.build()

# Try to get a series directory and check its metadata
series_all = tree.root.find_child('Series').find_child('All')
print(f'Series/All children: {len(series_all.children)}')

# Check first series directory
for child in series_all.children[:3]:
    print(f'\nSeries: {child.name}')
    print(f'  Metadata: {child.metadata}')
