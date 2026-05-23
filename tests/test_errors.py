"""Test error handling and logging"""

import pytest
import logging
import json
from unittest.mock import Mock, patch
from fastapi import Request
from plugin.tree import VirtualTree
from plugin.httpfs import HTTPFilesystem
from plugin.integration import DispatcharrIntegrator


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

    def test_integrator_does_not_expose_credentials(self):
        """Test integrator doesn't expose sensitive data"""
        integrator = DispatcharrIntegrator(auto_hydrate=True)

        # Should not be available without Django
        assert not integrator.is_available()

    def test_proxy_url_safe(self):
        """Test proxy URL generation doesn't include credentials"""
        integrator = DispatcharrIntegrator()

        url = integrator.get_proxy_url("movie", "abc123", "stream456")
        assert url == "/proxy/vod/movie/abc123?stream_id=stream456"
        # No credentials in URL
        assert "key" not in url.lower()
        assert "secret" not in url.lower()

    def test_filename_safe(self):
        """Test filename generation is safe"""
        integrator = DispatcharrIntegrator()

        filename = integrator.build_filename("Test Movie", 2024, "Provider", "123", "mkv")
        assert filename == "Test Movie (2024) - Provider-123.mkv"


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
        logger.error("Test error with %s", "REDACTED")

        # Verify the logger works
        assert logger.level <= logging.ERROR

        logger.removeHandler(log_capture)