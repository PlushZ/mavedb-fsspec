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
    score_set_collections = ("score-sets", "my-score-sets")
    score_set_files = ("scores.csv", "counts.csv", "variants.csv", "metadata.json", "mapped-variants.json")
    core_score_set_files = ("scores.csv", "counts.csv", "variants.csv", "metadata.json")

    def __init__(
        self,
        *args: Any,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.client = MaveDBClient(base_url=base_url, api_key=api_key, timeout=timeout)

    def ls(self, path: str, detail: bool = True, **kwargs: Any) -> list[Any]:
        normalized = self._normalize_path(path)

        if normalized in {"", "/"}:
            entries = [self._directory_info("score-sets")]
            if self.client.has_api_key:
                entries.append(self._directory_info("my-score-sets"))
        elif normalized in self.score_set_collections:
            entries, _ = self.list_score_sets(
                collection=normalized,
                limit=kwargs.get("limit"),
                offset=kwargs.get("offset", 0),
                query=kwargs.get("query"),
            )
        elif self._is_score_set_collection_path(normalized):
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
        if normalized in self.score_set_collections:
            if normalized == "my-score-sets" and not self.client.has_api_key:
                raise PermissionError("An API key is required to list my-score-sets.")
            return self._directory_info(normalized)
        if self._is_score_set_collection_path(normalized):
            parts = normalized.split("/")
            if len(parts) == 2:
                return self._directory_info(normalized)
            if len(parts) == 3 and parts[2] in self.score_set_files:
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
        if len(parts) != 3 or parts[0] not in self.score_set_collections:
            raise MaveDBPathError(f"Unsupported MaveDB path: {path}")

        urn = parts[1]
        filename = parts[2]
        endpoint = self._endpoint_for_score_set_file(urn, filename)
        data = self.client.get_bytes(endpoint)
        if filename.endswith(".json"):
            return self._escape_html_like_json_content(data)
        return data

    def list_score_sets(
        self,
        collection: str = "score-sets",
        limit: int | None = None,
        offset: int | None = 0,
        query: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        collection = self._normalize_collection(collection)
        if collection == "my-score-sets" and not self.client.has_api_key:
            raise PermissionError("An API key is required to list my-score-sets.")

        score_sets, total_count = self._search_score_sets(
            collection=collection,
            limit=min(limit or 100, 100),
            offset=offset or 0,
            query=query,
        )
        return self._score_sets_to_entries(score_sets, collection), total_count

    def _search_score_sets(
        self,
        collection: str,
        limit: int,
        offset: int,
        query: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        payload: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "include_experiment_score_set_urns_and_count": False,
        }
        if query:
            payload["text"] = query

        response = self.client.post_json(self._search_endpoint(collection), payload)
        score_sets = response.get("scoreSets", response.get("score_sets", []))
        total_count = int(response.get("numScoreSets", response.get("num_score_sets", len(score_sets))))
        return score_sets, total_count

    def _score_sets_to_entries(self, score_sets: list[dict[str, Any]], collection: str) -> list[dict[str, Any]]:
        entries = []
        for score_set in score_sets:
            urn = score_set["urn"]
            info = self._directory_info(f"{collection}/{urn}")
            title = self._score_set_display_title(score_set)
            if title:
                info["display_name"] = f"{title} ({urn})"
            entries.append(info)
        return entries

    @staticmethod
    def _score_set_display_title(score_set: dict[str, Any]) -> str | None:
        experiment = score_set.get("experiment")
        if isinstance(experiment, dict) and experiment.get("title"):
            return str(experiment["title"])
        if score_set.get("title"):
            return str(score_set["title"])
        return None

    def _search_endpoint(self, collection: str) -> str:
        if collection == "my-score-sets":
            return "me/score-sets/search"
        return "score-sets/search"

    def _normalize_collection(self, collection: str) -> str:
        normalized = self._normalize_path(collection)
        if normalized not in self.score_set_collections:
            raise FileNotFoundError(collection)
        return normalized

    def _is_score_set_collection_path(self, path: str) -> bool:
        return any(path.startswith(f"{collection}/") for collection in self.score_set_collections)

    def _score_set_entries(self, path: str) -> list[dict[str, Any]]:
        parts = path.split("/")
        if len(parts) == 2:
            entries = [self._file_info(f"{path}/{filename}") for filename in self.core_score_set_files]
            if self._score_set_file_exists(parts[1], "mapped-variants.json"):
                entries.append(self._file_info(f"{path}/mapped-variants.json"))
            return entries
        if len(parts) == 3 and parts[2] in self.score_set_files:
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

    def _score_set_file_exists(self, urn: str, filename: str) -> bool:
        return self.client.exists(self._endpoint_for_score_set_file(urn, filename))

    def _normalize_path(self, path: str) -> str:
        stripped = self._strip_protocol(path)
        return stripped.strip("/")

    @staticmethod
    def _escape_html_like_json_content(data: bytes) -> bytes:
        return data.replace(b"<", b"\\u003c").replace(b">", b"\\u003e")

    def _directory_info(self, name: str) -> dict[str, Any]:
        return {"name": name, "type": "directory", "size": 0}

    def _file_info(self, name: str) -> dict[str, Any]:
        return {"name": name, "type": "file", "size": 0}
