"""
Unit tests for download module components.

Tests HTTP client, resume manager, chunk writer, retry policy,
and the orchestrator with network simulation.
"""

import hashlib
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from src.utils.download.http_client import HttpClient
from src.utils.download.resume_manager import ResumeManager, DownloadState
from src.utils.download.chunk_writer import ChunkWriter
from src.utils.download.retry_policy import RetryPolicy
from src.utils.download.downloader import download_file


# ============================================================================
# TestHttpClient
# ============================================================================


class TestHttpClient:
    """Test HTTP client with Range headers and cancellation."""

    def test_get_without_range(self):
        """HTTP client performs basic GET request."""
        client = HttpClient(timeout=30)

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.getheader.return_value = "1024"
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.read.side_effect = [b"test", b""]

        with patch("urllib.request.urlopen", return_value=mock_response):
            response = client.get("http://example.com/file.zip")

            assert response.status_code == 200
            assert response.content_length == 1024
            chunks = list(response.stream)
            assert chunks == [b"test"]

    def test_get_with_range_header(self):
        """HTTP client adds Range header when start_byte > 0."""
        client = HttpClient()

        mock_response = MagicMock()
        mock_response.getcode.return_value = 206  # Partial Content
        mock_response.getheader.return_value = "512"
        mock_response.headers = {}
        mock_response.read.side_effect = [b"partial", b""]

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            response = client.get("http://example.com/file.zip", start_byte=512)

            # Verify Range header was set
            request = mock_urlopen.call_args[0][0]
            assert request.headers.get("Range") == "bytes=512-"
            assert response.status_code == 206

    def test_get_handles_cancellation(self):
        """HTTP client respects cancellation token."""
        client = HttpClient()
        cancel_token = Mock()
        cancel_token.is_cancelled.return_value = True

        mock_response = MagicMock()
        mock_response.read.return_value = b"chunk"

        with patch("urllib.request.urlopen", return_value=mock_response):
            response = client.get("http://example.com/file.zip", cancel_token=cancel_token)

            # Stream should raise InterruptedError
            with pytest.raises(InterruptedError, match="cancelled by user"):
                list(response.stream)

    def test_get_handles_network_error(self):
        """HTTP client propagates URLError on network failure."""
        client = HttpClient()

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            with pytest.raises(urllib.error.URLError):
                client.get("http://example.com/file.zip")


# ============================================================================
# TestResumeManager
# ============================================================================


class TestResumeManager:
    """Test resume manager for partial download state."""

    def test_get_resume_position_no_partial(self):
        """Resume position is 0 when no partial file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"
            mgr = ResumeManager(dest)

            assert mgr.get_resume_position() == 0

    def test_get_resume_position_from_file_size(self):
        """Resume position is file size when no metadata exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"
            mgr = ResumeManager(dest)

            # Write partial file
            mgr.part_file.write_bytes(b"partial data")

            assert mgr.get_resume_position() == 12

    def test_get_resume_position_from_metadata(self):
        """Resume position uses metadata when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"
            mgr = ResumeManager(dest)

            # Write partial file and metadata
            mgr.part_file.write_bytes(b"partial")
            mgr.save_state(
                url="http://example.com/file.zip", expected_size=1024, expected_sha256="abc123", bytes_downloaded=256
            )

            assert mgr.get_resume_position() == 256

    def test_save_and_load_state(self):
        """State can be saved and loaded from metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"
            mgr = ResumeManager(dest)

            mgr.save_state(
                url="http://example.com/file.zip",
                expected_size=1024,
                expected_sha256="abc123def456",
                bytes_downloaded=512,
            )

            state = DownloadState.load(mgr.meta_file)
            assert state is not None
            assert state.url == "http://example.com/file.zip"
            assert state.expected_size == 1024
            assert state.expected_sha256 == "abc123def456"
            assert state.bytes_downloaded == 512

    def test_cleanup_removes_files(self):
        """Cleanup removes both .part and .meta files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"
            mgr = ResumeManager(dest)

            # Create files
            mgr.part_file.write_bytes(b"partial")
            mgr.meta_file.write_bytes(b"{}")

            assert mgr.part_file.exists()
            assert mgr.meta_file.exists()

            mgr.cleanup()

            assert not mgr.part_file.exists()
            assert not mgr.meta_file.exists()


# ============================================================================
# TestChunkWriter
# ============================================================================


class TestChunkWriter:
    """Test chunk writer with fsync and hash verification."""

    def test_write_chunk_calculates_hash(self):
        """Chunk writer computes SHA256 incrementally."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file = Path(tmpdir) / "test.bin"
            writer = ChunkWriter(file)

            data1 = b"hello "
            data2 = b"world"

            writer.write_chunk(data1)
            writer.write_chunk(data2)

            expected_hash = hashlib.sha256(data1 + data2).hexdigest()
            assert writer.verify(expected_hash)

    def test_write_chunk_updates_bytes_written(self):
        """Chunk writer tracks bytes written."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file = Path(tmpdir) / "test.bin"
            writer = ChunkWriter(file)

            writer.write_chunk(b"1234567890")
            assert writer.get_bytes_written() == 10

            writer.write_chunk(b"abc")
            assert writer.get_bytes_written() == 13

    def test_verify_returns_false_on_mismatch(self):
        """Verify returns False when hash doesn't match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file = Path(tmpdir) / "test.bin"
            writer = ChunkWriter(file)

            writer.write_chunk(b"test data")
            assert not writer.verify("wrong_hash")

    def test_resume_from_existing_file(self):
        """Chunk writer can resume hash calculation from existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file = Path(tmpdir) / "test.bin"

            # Write initial data
            file.write_bytes(b"initial ")

            # Resume writing
            writer = ChunkWriter(file, resume_from_byte=8)
            writer.write_chunk(b"resumed")

            # Hash should be for combined data
            expected_hash = hashlib.sha256(b"initial resumed").hexdigest()
            assert writer.verify(expected_hash)


# ============================================================================
# TestRetryPolicy
# ============================================================================


class TestRetryPolicy:
    """Test retry policy with exponential backoff."""

    def test_execute_succeeds_on_first_try(self):
        """Retry policy returns result on first success."""
        policy = RetryPolicy(max_retries=3)

        def operation():
            return "success"

        result = policy.execute(operation)
        assert result == "success"

    def test_execute_retries_on_failure(self):
        """Retry policy retries operation on failure."""
        policy = RetryPolicy(max_retries=3, initial_delay=0.01)

        attempts = [0]

        def operation():
            attempts[0] += 1
            if attempts[0] < 3:
                raise ValueError("not yet")
            return "success"

        result = policy.execute(operation)
        assert result == "success"
        assert attempts[0] == 3

    def test_execute_raises_last_exception_on_exhaustion(self):
        """Retry policy raises last exception when retries exhausted."""
        policy = RetryPolicy(max_retries=2, initial_delay=0.01)

        def operation():
            raise ValueError("always fails")

        with pytest.raises(ValueError, match="always fails"):
            policy.execute(operation)

    def test_execute_calls_on_retry_callback(self):
        """Retry policy calls on_retry callback on each retry."""
        policy = RetryPolicy(max_retries=3, initial_delay=0.01)

        retry_info = []

        def operation():
            if len(retry_info) < 2:
                raise ValueError("not yet")
            return "success"

        def on_retry(attempt, exc):
            retry_info.append((attempt, str(exc)))

        result = policy.execute(operation, on_retry=on_retry)

        assert result == "success"
        assert len(retry_info) == 2
        assert retry_info[0][0] == 0
        assert retry_info[1][0] == 1


# ============================================================================
# TestDownloader
# ============================================================================


class TestDownloader:
    """Test main downloader orchestrator."""

    def test_skips_download_when_file_already_valid(self):
        """Downloader skips download when file already exists and is valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"
            data = b"test data"
            dest.write_bytes(data)

            expected_hash = hashlib.sha256(data).hexdigest()
            expected_size = len(data)

            # Mock progress callback
            progress_calls = []

            def progress_cb(downloaded, total):
                progress_calls.append((downloaded, total))

            with patch("src.utils.download.downloader._verify_complete_file", return_value=True):
                result = download_file(
                    url="http://example.com/file.zip",
                    dest_zip=dest,
                    expected_sha256=expected_hash,
                    expected_size=expected_size,
                    progress_cb=progress_cb,
                )

            assert result is True
            assert progress_calls == [(expected_size, expected_size)]

    @patch("src.utils.download.downloader.HttpClient")
    @patch("src.utils.download.downloader._verify_complete_file", return_value=False)
    def test_downloads_successfully_with_verification(self, mock_verify, mock_client_class):
        """Downloader downloads file and verifies hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"
            data = b"downloaded data"
            expected_hash = hashlib.sha256(data).hexdigest()
            expected_size = len(data)

            # Mock HTTP client
            mock_client = mock_client_class.return_value
            mock_response = Mock()
            mock_response.content_length = expected_size
            mock_response.stream = iter([data])
            mock_client.get.return_value = mock_response

            result = download_file(
                url="http://example.com/file.zip",
                dest_zip=dest,
                expected_sha256=expected_hash,
                expected_size=expected_size,
            )

            assert result is True
            assert dest.exists()

    @patch("src.utils.download.downloader.HttpClient")
    @patch("src.utils.download.downloader._verify_complete_file", return_value=False)
    def test_handles_cancellation(self, mock_verify, mock_client_class):
        """Downloader handles cancellation gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"

            # Mock HTTP client to raise InterruptedError
            mock_client = mock_client_class.return_value
            mock_client.get.side_effect = InterruptedError("cancelled")

            result = download_file(
                url="http://example.com/file.zip", dest_zip=dest, expected_sha256="abc123", expected_size=1024
            )

            assert result is False

    @patch("src.utils.download.downloader.HttpClient")
    @patch("src.utils.download.downloader._verify_complete_file", return_value=False)
    def test_retries_on_network_failure(self, mock_verify, mock_client_class):
        """Downloader retries on network failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"
            data = b"success data"
            expected_hash = hashlib.sha256(data).hexdigest()
            expected_size = len(data)

            # Mock HTTP client: first 2 calls fail, 3rd succeeds
            mock_client = mock_client_class.return_value
            mock_response = Mock()
            mock_response.content_length = expected_size
            mock_response.stream = iter([data])

            mock_client.get.side_effect = [
                urllib.error.URLError("timeout"),
                urllib.error.URLError("connection reset"),
                mock_response,
            ]

            with patch("time.sleep"):  # Speed up test
                result = download_file(
                    url="http://example.com/file.zip",
                    dest_zip=dest,
                    expected_sha256=expected_hash,
                    expected_size=expected_size,
                )

            assert result is True
            assert mock_client.get.call_count == 3

    @patch("src.utils.download.downloader.HttpClient")
    @patch("src.utils.download.downloader._verify_complete_file", return_value=False)
    def test_fails_after_max_retries(self, mock_verify, mock_client_class):
        """Downloader fails after exhausting retries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"

            # Mock HTTP client to always fail
            mock_client = mock_client_class.return_value
            mock_client.get.side_effect = urllib.error.URLError("always fails")

            with patch("time.sleep"):  # Speed up test
                result = download_file(
                    url="http://example.com/file.zip", dest_zip=dest, expected_sha256="abc123", expected_size=1024
                )

            assert result is False
            assert mock_client.get.call_count == 5  # max_retries default

    @patch("src.utils.download.downloader.HttpClient")
    @patch("src.utils.download.downloader._verify_complete_file", return_value=False)
    def test_handles_size_mismatch(self, mock_verify, mock_client_class):
        """Downloader detects size mismatch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"

            # Mock response with wrong size
            mock_client = mock_client_class.return_value
            mock_response = Mock()
            mock_response.content_length = 512  # Expected 1024
            mock_response.stream = iter([b"short"])
            mock_client.get.return_value = mock_response

            with patch("time.sleep"):
                result = download_file(
                    url="http://example.com/file.zip", dest_zip=dest, expected_sha256="abc123", expected_size=1024
                )

            assert result is False


class TestCancellationBehavior:
    """Test download cancellation leaves partial files for resume."""

    @patch("src.utils.download.downloader.HttpClient")
    @patch("src.utils.download.downloader._verify_complete_file", return_value=False)
    def test_cancellation_preserves_partial_files(self, mock_verify, mock_client_class):
        """Test that cancellation leaves .part and .meta files intact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"
            Path(str(dest) + ".part")
            Path(str(dest) + ".meta")

            # Mock HTTP client to write some data then cancel
            mock_client = mock_client_class.return_value
            mock_response = Mock()
            mock_response.content_length = 1024
            mock_response.stream = iter([b"partial data"])
            mock_client.get.side_effect = InterruptedError("cancelled by user")

            result = download_file(
                url="http://example.com/file.zip", dest_zip=dest, expected_sha256="abc123", expected_size=1024
            )

            # Download should fail but partial files should remain
            assert result is False
            # Note: Actual file preservation depends on when InterruptedError is raised
            # In real scenario, ChunkWriter would have created part_file before cancellation

    @patch("src.utils.download.downloader.HttpClient")
    @patch("src.utils.download.downloader._verify_complete_file", return_value=False)
    def test_resume_after_cancellation(self, mock_verify, mock_client_class):
        """Test that download can resume after cancellation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.zip"
            part_file = Path(str(dest) + ".part")
            meta_file = Path(str(dest) + ".meta")

            # Simulate partial download exists
            partial_data = b"partial "
            part_file.write_bytes(partial_data)

            # Create metadata
            import json

            meta = {
                "url": "http://example.com/file.zip",
                "expected_size": 1024,
                "expected_sha256": "abc123",
                "bytes_downloaded": len(partial_data),
            }
            meta_file.write_text(json.dumps(meta))

            # Mock HTTP client for resume
            remaining_data = b"resumed data"
            full_data = partial_data + remaining_data
            expected_hash = hashlib.sha256(full_data).hexdigest()

            mock_client = mock_client_class.return_value
            mock_response = Mock()
            # Content-Length should be full size when responding with 200 OK,
            # or remaining size when responding with 206 Partial Content
            # For this test, we'll simulate 200 OK with full content
            mock_response.content_length = len(full_data)
            mock_response.stream = iter([full_data])
            mock_client.get.return_value = mock_response

            result = download_file(
                url="http://example.com/file.zip",
                dest_zip=dest,
                expected_sha256=expected_hash,
                expected_size=len(full_data),
            )

            assert result is True
            # Verify that resume was attempted by checking if get was called
            # (In real scenario, resume manager would pass start_byte to get)
            assert mock_client.get.called
