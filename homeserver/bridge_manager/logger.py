"""
Logging for bridge manager.

Two main loggers:
1. BridgeLogger - stdout/file logging for general application events
2. RequestTracker - database logging for all proxied requests and responses
"""

import json
import uuid
import time
import logging
from typing import Optional, Dict, Any

from .database.repositories import RequestLogRepository


class RequestTracker:
    """
    Tracks a request-response cycle and logs to database.

    Automatically handles:
    - Unique request ID generation
    - Timing (duration_ms)
    - JSON parsing of request/response bodies
    - Header sanitization (removes authorization)
    - Database persistence via RequestLogRepository

    Use this to track all incoming requests and their responses.

    Example:
        tracker = RequestTracker(
            source="homeserver",
            method="POST",
            path="/transactions/123",
            bridge_id=1,
            headers=request.headers,
            body=request.body
        )
        # ... handle request ...
        tracker.log_response(status_code=200, response_body=response.content)
    """

    def __init__(
        self,
        source: str,  # "homeserver" or "bridge"
        method: str,
        path: str,
        bridge_id: Optional[int] = None,
        discovery_method: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        body: Optional[bytes] = None,
        forwarded_to: Optional[str] = None,
    ):
        """
        Initialize a request tracker.

        Args:
            source: Where the request came from ("homeserver" or "bridge")
            method: HTTP method (GET, POST, etc.)
            path: Request path
            bridge_id: Associated bridge ID (optional)
            discovery_method: How the bridge was identified (optional)
            query_params: Query parameters (optional)
            headers: Request headers (optional, authorization will be excluded)
            body: Raw request body (optional)
            forwarded_to: Where the request was proxied to (optional)
        """
        self.request_id = str(uuid.uuid4())
        self.source = source
        self.start_time = time.time()
        self.repository = RequestLogRepository()

        # Parse and sanitize headers (remove auth)
        safe_headers = {}
        if headers:
            safe_headers = {
                k: v for k, v in headers.items() if k.lower() != "authorization"
            }

        # Parse body if it's JSON
        body_dict = None
        if body:
            try:
                body_dict = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # Build raw incoming request snapshot for debugging
        raw_incoming = {
            "method": method,
            "path": path,
            "query_params": query_params or {},
            "headers": safe_headers,
            "body": body_dict,
        }

        # Log the incoming request
        try:
            self.repository.create(
                request_id=self.request_id,
                source=source,
                direction="inbound",
                bridge_id=bridge_id,
                discovery_method=discovery_method,
                method=method,
                path=path,
                query_params=query_params or {},
                headers=safe_headers,
                body=body_dict,
                forwarded_to=forwarded_to,
                raw_incoming_request=raw_incoming,
            )
        except Exception:
            # Fail silently - don't crash if logging fails
            pass

    def log_outgoing_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        body: Optional[bytes] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record the outgoing (forwarded) request for debugging.
        Call this after token replacement, just before sending.

        Args:
            method: HTTP method used for the forwarded request
            url: Full target URL the request was forwarded to
            headers: Outgoing headers (authorization will be excluded)
            body: Raw outgoing request body
            query_params: Query parameters
        """
        safe_headers = {}
        if headers:
            safe_headers = {
                k: v for k, v in headers.items() if k.lower() != "authorization"
            }

        body_dict = None
        if body:
            try:
                body_dict = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        raw_outgoing = {
            "method": method,
            "url": url,
            "query_params": query_params or {},
            "headers": safe_headers,
            "body": body_dict,
        }

        try:
            self.repository.update_response(
                request_id=self.request_id,
                status_code=0,  # placeholder until real response
                raw_outgoing_request=raw_outgoing,
            )
        except Exception:
            pass

    def set_bridge_context(
        self,
        bridge_id: int,
        discovery_method: Optional[str] = None,
    ) -> None:
        """
        Update the log row with bridge context once the bridge has been identified.
        Call this as soon as the bridge is known.

        Args:
            bridge_id: Database ID of the identified bridge
            discovery_method: How the bridge was identified (optional)
        """
        try:
            self.repository.update_bridge_context(
                request_id=self.request_id,
                bridge_id=bridge_id,
                discovery_method=discovery_method,
            )
        except Exception:
            pass

    def log_response(
        self,
        status_code: int,
        response_body: Optional[bytes] = None,
        error: Optional[str] = None,
        response_source: Optional[str] = None,
    ) -> None:
        """
        Log the response for this request.

        Args:
            status_code: HTTP status code from response
            response_body: Raw response body (optional)
            error: Error message if request failed (optional)
            response_source: Who produced the response — "appservice" (generated
                internally, e.g. auth failure) or "upstream" (from the HS/bridge)
        """
        duration_ms = int((time.time() - self.start_time) * 1000)

        # Parse response body if it's JSON
        response_dict = None
        if response_body:
            try:
                response_dict = json.loads(response_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        try:
            self.repository.update_response(
                request_id=self.request_id,
                status_code=status_code,
                response_body=response_dict,
                duration_ms=duration_ms,
                error=error,
                response_source=response_source,
            )
        except Exception:
            # Fail silently - don't crash if logging fails
            pass


class BridgeLogger:
    """
    Simple logger for stdout/file logging of application events.

    Provides basic logging methods: info, error, warning, debug, success.
    """

    def __init__(self):
        """Initialize logger."""
        self._logger = logging.getLogger("bridge_manager")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def log_info(self, message: str):
        """Log info message."""
        self._logger.info(message)

    def log_error(self, message: str):
        """Log error message."""
        self._logger.error(message)

    def log_warning(self, message: str):
        """Log warning message."""
        self._logger.warning(message)

    def log_debug(self, message: str):
        """Log debug message."""
        self._logger.debug(message)

    def log_success(self, message: str):
        """Log success message."""
        self._logger.info(f"✅ {message}")
