"""HTTP client helpers for the MaveDB API."""

from __future__ import annotations

from typing import Any

import httpx

from mavedb_fsspec.errors import MaveDBAPIError

DEFAULT_BASE_URL = "https://api.mavedb.org/api/v1"


class MaveDBClient:
    """Small synchronous client for MaveDB API resources."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers: dict[str, str] = {}
        if api_key:
            self.headers["X-API-key"] = api_key
        self.has_api_key = bool(api_key)
        self._session = httpx.Client(
            base_url=f"{self.base_url}/",
            headers=self.headers,
            timeout=self.timeout,
        )

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> MaveDBClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        response = self._session.get(path.lstrip("/"), params=params)
        self._raise_for_status(response)
        return response

    def head(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        response = self._session.head(path.lstrip("/"), params=params)
        self._raise_for_status(response)
        return response

    def get_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        return self.get(path, params=params).content

    def post_json(self, path: str, json: dict[str, Any] | None = None) -> Any:
        response = self._session.post(path.lstrip("/"), json=json)
        self._raise_for_status(response)
        return response.json()

    def exists(self, path: str, params: dict[str, Any] | None = None) -> bool:
        try:
            response = self._session.head(path.lstrip("/"), params=params)
            if response.status_code == 405:
                with self._session.stream("GET", path.lstrip("/"), params=params) as stream_response:
                    self._raise_for_status(stream_response)
                    return True
            self._raise_for_status(response)
        except FileNotFoundError:
            return False
        return True

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise FileNotFoundError(str(exc.request.url)) from exc
            raise MaveDBAPIError(exc.response.status_code, str(exc.request.url)) from exc
