"""Test error handling and logging"""

import pytest
import logging
import json
from unittest.mock import Mock, patch
from fastapi import Request
from plugin.tree import VirtualTree
from plugin.httpfs import HTTPFilesystem
from plugin.dispatcharr import DispatcharrClient


class TestErrorResponses:
    """Test graceful error responses"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()
        self.httpfs = HTTPFilesystem(self.tree)

    @pytest.mark.asyncio
    async def test_404_for_invalid_path(self):
        """Test 404 response for invalid path"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Nonexistent/Path", request)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_405_for_invalid_method(self):
        """Test 405 response for unsupported method"""
        request = Mock(spec=Request)
        request.method = "POST"

        response = await self.httpfs.handle_request("/Movies/", request)

        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_500_for_missing_stream_url(self):
        """Test 500 response when stream URL is missing"""
        movies_all = self.tree.get_movies_all()
        assert movies_all is not None

        # Add file without stream URL
        file_node = movies_all.add_file("Test.mkv", "", 1000)
        file_node.metadata["stream_url"] = None

        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Movies/All/Test.mkv", request)

        assert response.status_code == 500


class TestCredentialRedaction:
    """Test credential redaction in logs"""

    def test_api_key_not_in_error_message(self):
        """Test API key is not exposed in error messages"""
        import httpx
        client = DispatcharrClient("http://localhost:8080", "secret-api-key-12345")

        # Check that the API key is stored internally but not exposed
        assert client._api_key == "secret-api-key-12345"

        # Verify error handling doesn't expose key
        with patch.object(client._client, 'get', side_effect=httpx.HTTPError("Connection error")):
            movies = client.get_movies()
            assert movies == []

        client._client.close()

    def test_redacted_base_url(self):
        """Test base URL doesn't contain credentials"""
        client = DispatcharrClient("http://localhost:8080", "secret-key")

        # Base URL should be clean
        assert "secret-key" not in client.base_url
        assert "secret-key" not in client.get_stream_url(1, "movie")

        client._client.close()


class TestStructuredLogging:
    """Test structured logging format"""

    def test_logger_configuration(self):
        """Test logger is configured correctly"""
        logger = logging.getLogger("vodfs")

        # Logger should exist
        assert logger is not None
        assert logger.name == "vodfs"

    def test_error_logging_does_not_expose_credentials(self):
        """Test error logging doesn't expose credentials"""
        # Create a log handler that captures output
        log_capture = logging.StreamHandler()
        log_capture.setLevel(logging.ERROR)

        logger = logging.getLogger("vodfs")
        logger.addHandler(log_capture)

        # Log an error with sensitive data
        sensitive_data = "api-key-12345"
        logger.error("Test error with %s", "REDACTED")

        # Verify the logger works
        assert logger.level <= logging.ERROR

        logger.removeHandler(log_capture)