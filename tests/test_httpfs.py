"""Test HTTP filesystem handlers"""

import pytest
from unittest.mock import Mock, MagicMock
from fastapi import Request
from plugin.tree import DirectoryNode, FileNode, VirtualTree
from plugin.httpfs import HTTPFilesystem


class TestHTTPFilesystem:
    """Test HTTP filesystem request handlers"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()

        # Build test structure
        movies = self.tree.get_movies_root()
        all_dir = movies.add_directory("All")
        all_dir.add_file("Test.mkv", "http://example.com/stream.mkv", 1234567890)

        self.httpfs = HTTPFilesystem(self.tree)

    @pytest.mark.asyncio
    async def test_handle_get_root(self):
        """Test GET request to root"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/", request)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_handle_get_directory_without_trailing_slash(self):
        """Test GET request to directory without trailing slash"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Movies", request)
        assert response.status_code == 301
        assert "Movies/" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_handle_get_directory(self):
        """Test GET request to directory"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Movies/", request)
        assert response.status_code == 200
        content = response.body.decode()
        assert "Index of /Movies/" in content

    @pytest.mark.asyncio
    async def test_handle_get_file(self):
        """Test GET request to file"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Movies/All/Test.mkv", request)
        assert response.status_code == 302
        assert "http://example.com/stream.mkv" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_handle_get_not_found(self):
        """Test GET request to non-existent path"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Invalid/Path", request)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_handle_head_directory(self):
        """Test HEAD request to directory"""
        request = Mock(spec=Request)
        request.method = "HEAD"

        response = await self.httpfs.handle_head("/Movies/", request)
        assert response.status_code == 200
        assert response.headers.get("content-type") == "text/html; charset=utf-8"

    @pytest.mark.asyncio
    async def test_handle_head_file(self):
        """Test HEAD request to file"""
        request = Mock(spec=Request)
        request.method = "HEAD"

        response = await self.httpfs.handle_head("/Movies/All/Test.mkv", request)
        assert response.status_code == 200
        assert response.headers.get("content-length") == "1234567890"
        assert response.headers.get("accept-ranges") == "bytes"

    @pytest.mark.asyncio
    async def test_handle_invalid_method(self):
        """Test unsupported HTTP method"""
        request = Mock(spec=Request)
        request.method = "POST"

        response = await self.httpfs.handle_request("/Movies/", request)
        assert response.status_code == 405


class TestDirectoryListing:
    """Test directory listing HTML generation"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()

        # Build test structure
        movies = self.tree.get_movies_root()
        all_dir = movies.add_directory("All")
        all_dir.add_file("Movie1.mkv", "http://example.com/stream1.mkv", 1000)
        all_dir.add_file("Movie2.mkv", "http://example.com/stream2.mkv", 2000)
        all_dir.add_directory("Category1")

        self.httpfs = HTTPFilesystem(self.tree)

    @pytest.mark.asyncio
    async def test_directory_listing_html(self):
        """Test directory listing HTML generation"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Movies/All/", request)
        content = response.body.decode()

        # Check HTML structure
        assert "<!DOCTYPE html>" in content
        assert "<title>Index of /Movies/All/</title>" in content
        assert "<table>" in content
        assert "<th>Name</th>" in content
        assert "<th>Size</th>" in content

        # Check parent link
        assert "../" in content

        # Check files and directories
        assert "Movie1.mkv" in content
        assert "Movie2.mkv" in content
        assert "Category1/" in content

    @pytest.mark.asyncio
    async def test_directory_listing_sorting(self):
        """Test directories are sorted before files"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Movies/All/", request)
        content = response.body.decode()

        # Find positions
        cat_pos = content.find("Category1/")
        movie1_pos = content.find("Movie1.mkv")
        movie2_pos = content.find("Movie2.mkv")

        # Directories should come first
        assert cat_pos < movie1_pos
        assert cat_pos < movie2_pos

        # Files should be sorted alphabetically
        assert movie1_pos < movie2_pos


class TestFileRedirect:
    """Test file redirect to stream URL"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()

        movies = self.tree.get_movies_root()
        all_dir = movies.add_directory("All")
        all_dir.add_file("Test.mkv", "http://example.com/stream.mkv")

        self.httpfs = HTTPFilesystem(self.tree)

    @pytest.mark.asyncio
    async def test_file_redirects_to_stream_url(self):
        """Test file request returns 302 redirect"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Movies/All/Test.mkv", request)
        assert response.status_code == 302
        assert response.headers["location"] == "http://example.com/stream.mkv"

    @pytest.mark.asyncio
    async def test_file_with_multiple_streams(self):
        """Test multiple streams for same title"""
        movies = self.tree.get_movies_root()
        all_dir = movies.add_directory("All")
        all_dir.add_file("Test - Provider1-stream1.mkv", "http://p1.com/s1.mkv")
        all_dir.add_file("Test - Provider2-stream2.mkv", "http://p2.com/s2.mkv")

        request = Mock(spec=Request)
        request.method = "GET"

        response1 = await self.httpfs.handle_get("/Movies/All/Test - Provider1-stream1.mkv", request)
        response2 = await self.httpfs.handle_get("/Movies/All/Test - Provider2-stream2.mkv", request)

        assert response1.status_code == 302
        assert response1.headers["location"] == "http://p1.com/s1.mkv"
        assert response2.status_code == 302
        assert response2.headers["location"] == "http://p2.com/s2.mkv"


class TestHEADResponse:
    """Test HEAD response headers"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()

        movies = self.tree.get_movies_root()
        all_dir = movies.add_directory("All")

        # File with full metadata
        file_node = all_dir.add_file("Full.mkv", "http://example.com/full.mkv", 999999)
        file_node.metadata["content_type"] = "video/x-matroska"
        file_node.metadata["last_modified"] = "Mon, 20 May 2026 12:00:00 GMT"

        self.httpfs = HTTPFilesystem(self.tree)

    @pytest.mark.asyncio
    async def test_head_includes_all_headers(self):
        """Test HEAD response includes all required headers"""
        request = Mock(spec=Request)
        request.method = "HEAD"

        response = await self.httpfs.handle_head("/Movies/All/Full.mkv", request)

        assert response.status_code == 200
        assert response.headers["accept-ranges"] == "bytes"
        assert response.headers["content-length"] == "999999"
        assert response.headers["content-type"] == "video/x-matroska"
        assert response.headers["last-modified"] == "Mon, 20 May 2026 12:00:00 GMT"

    @pytest.mark.asyncio
    async def test_head_defaults(self):
        """Test HEAD response uses defaults when metadata missing"""
        request = Mock(spec=Request)
        request.method = "HEAD"

        # Create file without explicit metadata
        movies = self.tree.get_movies_root()
        all_dir = movies.add_directory("All")
        all_dir.add_file("Default.mkv", "http://example.com/default.mkv")

        response = await self.httpfs.handle_head("/Movies/All/Default.mkv", request)

        assert response.status_code == 200
        assert response.headers["accept-ranges"] == "bytes"
        assert response.headers["content-type"] == "application/octet-stream"


class TestRangeRequestSupport:
    """Test range request support for seekable playback"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()

        movies = self.tree.get_movies_root()
        all_dir = movies.add_directory("All")
        all_dir.add_file("Test.mkv", "http://example.com/stream.mkv", 1000000)

        self.httpfs = HTTPFilesystem(self.tree)

    @pytest.mark.asyncio
    async def test_head_includes_accept_ranges(self):
        """Test HEAD response includes Accept-Ranges header"""
        request = Mock(spec=Request)
        request.method = "HEAD"

        response = await self.httpfs.handle_head("/Movies/All/Test.mkv", request)

        assert response.status_code == 200
        assert response.headers["accept-ranges"] == "bytes"
        assert response.headers["content-length"] == "1000000"

    @pytest.mark.asyncio
    async def test_redirect_preserves_stream_url(self):
        """Test GET redirect preserves stream URL"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Movies/All/Test.mkv", request)

        assert response.status_code == 302
        assert "http://example.com/stream.mkv" in response.headers["location"]


class TestRcloneSimulation:
    """Test behavior simulating rclone mount access"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tree = VirtualTree()
        self.tree.build()

        movies = self.tree.get_movies_root()
        all_dir = movies.add_directory("All")
        all_dir.add_file("Movie.mkv", "http://proxy:8080/stream/1", 5000000)

        self.httpfs = HTTPFilesystem(self.tree)

    @pytest.mark.asyncio
    async def test_directory_listing_for_rclone(self):
        """Test directory listing works for rclone mount"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Movies/All/", request)

        assert response.status_code == 200
        content = response.body.decode()
        assert "Movie.mkv" in content

    @pytest.mark.asyncio
    async def test_file_redirect_for_playback(self):
        """Test file redirect works for playback"""
        request = Mock(spec=Request)
        request.method = "GET"

        response = await self.httpfs.handle_get("/Movies/All/Movie.mkv", request)

        assert response.status_code == 302
        assert response.headers["location"] == "http://proxy:8080/stream/1"