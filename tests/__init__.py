"""Test suite for vodfs plugin"""

import pytest

# This is the main test file that can be run with pytest
# Individual test files are:
# - test_tree.py: Virtual filesystem tree tests
# - test_httpfs.py: HTTP handler tests
# - test_integration.py: Dispatcharr integration tests

def test_example():
    """Example test to verify pytest is working"""
    assert True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])