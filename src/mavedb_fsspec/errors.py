"""Exceptions raised by mavedb-fsspec."""


class MaveDBFileSystemError(Exception):
    """Base exception for MaveDB filesystem errors."""


class MaveDBPathError(MaveDBFileSystemError):
    """Raised when a MaveDB filesystem path is invalid or unsupported."""


class MaveDBAPIError(MaveDBFileSystemError):
    """Raised when the MaveDB API returns an unexpected error."""

    def __init__(self, status_code: int, url: str):
        super().__init__(f"MaveDB API returned HTTP {status_code} for {url}")
        self.status_code = status_code
        self.url = url
