"""fsspec filesystem implementation for MaveDB."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from fsspec.spec import AbstractFileSystem

from mavedb_fsspec.client import DEFAULT_BASE_URL, MaveDBClient
from mavedb_fsspec.errors import MaveDBPathError


class MaveDBFileSystem(AbstractFileSystem):
    """Read-only fsspec filesystem for MaveDB score set data."""

    protocol = "mavedb"
    root_marker = ""

    def __init__(
        self,
        *args: Any,
        base_url: str = DEFAULT_BASE_URL,
        token: str | None = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.client = MaveDBClient(base_url=base_url, token=token, timeout=timeout)

    def ls(self, path: str, detail: bool = True, **kwargs: Any) -> list[Any]:
        normalized = self._normalize_path(path)

        if normalized in {"", "/"}:
            entries = [self._directory_info("score-sets")]
        elif normalized == "score-sets":
            entries = []
        elif normalized.startswith("score-sets/"):
            entries = self._score_set_entries(normalized)
        else:
            raise FileNotFoundError(path)

        if detail:
            return entries
        return [entry["name"] for entry in entries]

    def info(self, path: str, **kwargs: Any) -> dict[str, Any]:
        normalized = self._normalize_path(path)

        if normalized in {"", "/"}:
            return self._directory_info("")
        if normalized == "score-sets":
            return self._directory_info("score-sets")
        if normalized.startswith("score-sets/"):
            parts = normalized.split("/")
            if len(parts) == 2:
                return self._directory_info(normalized)
            if len(parts) == 3 and parts[2] in self._score_set_files():
                return self._file_info(normalized)

        raise FileNotFoundError(path)

    def cat_file(self, path: str, start: int | None = None, end: int | None = None, **kwargs: Any) -> bytes:
        data = self._read_score_set_file(path)
        return data[slice(start, end)]

    def _open(self, path: str, mode: str = "rb", **kwargs: Any) -> BytesIO:
        if mode != "rb":
            raise NotImplementedError("MaveDBFileSystem is read-only.")
        return BytesIO(self._read_score_set_file(path))

    def _read_score_set_file(self, path: str) -> bytes:
        normalized = self._normalize_path(path)
        parts = normalized.split("/")
        if len(parts) != 3 or parts[0] != "score-sets":
            raise MaveDBPathError(f"Unsupported MaveDB path: {path}")

        urn = parts[1]
        filename = parts[2]
        endpoint = self._endpoint_for_score_set_file(urn, filename)
        return self.client.get_bytes(endpoint)

    def _score_set_entries(self, path: str) -> list[dict[str, Any]]:
        parts = path.split("/")
        if len(parts) == 2:
            return [
                self._file_info(f"{path}/{filename}")
                for filename in self._score_set_files()
                if self._score_set_file_exists(parts[1], filename)
            ]
        if len(parts) == 3 and parts[2] in self._score_set_files():
            return [self._file_info(path)]
        raise FileNotFoundError(path)

    def _endpoint_for_score_set_file(self, urn: str, filename: str) -> str:
        endpoints = {
            "scores.csv": f"score-sets/{urn}/scores",
            "counts.csv": f"score-sets/{urn}/counts",
            "variants.csv": f"score-sets/{urn}/variants/data",
            "metadata.json": f"score-sets/{urn}",
            "mapped-variants.json": f"score-sets/{urn}/mapped-variants",
        }
        try:
            return endpoints[filename]
        except KeyError as exc:
            raise FileNotFoundError(filename) from exc

    def _score_set_files(self) -> tuple[str, ...]:
        return ("scores.csv", "counts.csv", "variants.csv", "metadata.json", "mapped-variants.json")

    def _score_set_file_exists(self, urn: str, filename: str) -> bool:
        return self.client.exists(self._endpoint_for_score_set_file(urn, filename))

    def _normalize_path(self, path: str) -> str:
        stripped = self._strip_protocol(path)
        return stripped.strip("/")

    def _directory_info(self, name: str) -> dict[str, Any]:
        return {"name": name, "type": "directory", "size": 0}

    def _file_info(self, name: str) -> dict[str, Any]:
        return {"name": name, "type": "file", "size": None}
