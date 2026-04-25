"""HTTP client helpers for the MaveDB API."""

from __future__ import annotations

from typing import Any

import httpx

from mavedb_fsspec.errors import MaveDBAPIError

DEFAULT_BASE_URL = "https://api.mavedb.org/api/v1"


class MaveDBClient:
    """Small synchronous client for public MaveDB API resources."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, token: str | None = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers: dict[str, str] = {}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = httpx.get(
            self._url(path),
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        return response.json()

    def get_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        response = httpx.get(
            self._url(path),
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        return response.content

    def exists(self, path: str, params: dict[str, Any] | None = None) -> bool:
        response = httpx.head(
            self._url(path),
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )
        if response.status_code == 405:
            response = httpx.get(
                self._url(path),
                params=params,
                headers=self.headers,
                timeout=self.timeout,
            )
        try:
            self._raise_for_status(response)
        except FileNotFoundError:
            return False
        return True

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise FileNotFoundError(str(exc.request.url)) from exc
            raise MaveDBAPIError(exc.response.status_code, str(exc.request.url)) from exc
