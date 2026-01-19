"""
HTTP Client with configurable timeout and cancellation support.

Provides clean HTTP abstraction for GET requests with Range headers,
streaming responses, and cancellation tokens.
"""

import logging
import ssl
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional, Iterator, Dict

logger = logging.getLogger(__name__)


# Configure SSL context for macOS Python (which lacks default CA certs)
def _create_ssl_context():
    """Create SSL context with certifi certificates for macOS compatibility."""
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
        logger.debug("Using certifi CA bundle for SSL: %s", certifi.where())
        return context
    except ImportError:
        logger.debug("certifi not available, using default SSL context")
        return ssl.create_default_context()


_SSL_CONTEXT = _create_ssl_context()


@dataclass
class HttpResponse:
    """HTTP response with content iterator."""

    status_code: int
    content_length: Optional[int]
    headers: Dict[str, str]
    stream: Iterator[bytes]


class HttpClient:
    """HTTP client with configurable timeout and headers."""

    def __init__(self, timeout: int = 30, user_agent: str = "USDXFixGap/1.0"):
        """
        Initialize HTTP client.

        Args:
            timeout: Request timeout in seconds
            user_agent: User-Agent header value
        """
        self.timeout = timeout
        self.user_agent = user_agent

    def get(self, url: str, start_byte: int = 0, cancel_token=None) -> HttpResponse:
        """
        Execute GET request with optional Range header.

        Args:
            url: URL to fetch
            start_byte: Starting byte for Range header (0 = no range)
            cancel_token: Optional CancelToken for cancellation

        Returns:
            HttpResponse with streaming content

        Raises:
            urllib.error.URLError: Network failure
            urllib.error.HTTPError: HTTP error response
            InterruptedError: Download cancelled
        """
        headers = {"User-Agent": self.user_agent}
        if start_byte > 0:
            headers["Range"] = f"bytes={start_byte}-"

        req = urllib.request.Request(url, headers=headers)

        try:
            response = urllib.request.urlopen(req, timeout=self.timeout, context=_SSL_CONTEXT)

            # Extract content length
            content_length_str = response.getheader("Content-Length")
            content_length = int(content_length_str) if content_length_str else None

            # Build headers dict
            headers_dict = dict(response.headers)

            return HttpResponse(
                status_code=response.getcode(),
                content_length=content_length,
                headers=headers_dict,
                stream=self._iter_content(response, cancel_token),
            )
        except urllib.error.URLError as e:
            logger.error(f"HTTP request failed: {e}")
            raise

    def _iter_content(self, response, cancel_token, chunk_size: int = 8192) -> Iterator[bytes]:
        """
        Iterate response content in chunks with cancellation.

        Args:
            response: urllib response object
            cancel_token: Optional CancelToken
            chunk_size: Chunk size in bytes

        Yields:
            Chunks of bytes

        Raises:
            InterruptedError: Download cancelled
        """
        while True:
            if cancel_token and cancel_token.is_cancelled():
                raise InterruptedError("Download cancelled by user")

            chunk = response.read(chunk_size)
            if not chunk:
                break
            yield chunk
