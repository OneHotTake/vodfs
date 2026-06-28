"""Unit tests for the enable-time base-URL validation in the root plugin.py.

Loaded by file path because a `plugin/` package shadows the `plugin.py` module name.
"""
import importlib.util
import os

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_root_plugin():
    spec = importlib.util.spec_from_file_location(
        "vodfs_root_plugin", os.path.join(_ROOT, "plugin.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


validate = _load_root_plugin().Plugin._validate_base_url


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:9191",
    "https://dispatcharr.example.com",
    "http://host:9191/",
])
def test_valid_urls_pass(url):
    assert validate(url) is None


@pytest.mark.parametrize("url", [
    "",
    "   ",
    "127.0.0.1:9191",        # no scheme
    "file:///etc/passwd",    # non-http scheme
    "ftp://host/x",
    "http://",               # no host
])
def test_invalid_urls_return_error(url):
    msg = validate(url)
    assert isinstance(msg, str) and msg
