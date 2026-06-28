"""Make the plugin's pure helpers importable without Dispatcharr/Django.

`integration.py` and `tree.py` guard their Django imports, so adding the
``plugin/`` directory to ``sys.path`` lets us import them standalone and unit-test
the pure naming/parsing functions in milliseconds.
"""
import os
import sys

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugin"))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)
