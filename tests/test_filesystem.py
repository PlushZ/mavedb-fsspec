import httpx
import pytest

from mavedb_fsspec import MaveDBFileSystem
from mavedb_fsspec.client import MaveDBClient


def response(
    content: bytes = b"",
    headers: dict[str, str] | None = None,
    url: str = "https://example.test/api/v1/score-sets/urn:mavedb:00000001-a-1",
) -> httpx.Response:
    return httpx.Response(200, content=content, headers=headers, request=httpx.Request("GET", url))


def filesystem(**kwargs) -> MaveDBFileSystem:
    return MaveDBFileSystem(base_url="https://example.test/api/v1", skip_instance_cache=True, **kwargs)


def test_filesystem_imports():
    fs = filesystem()

    assert fs.protocol == "mavedb"


def test_filesystem_instances_are_not_cached():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
    fs.close()

    next_fs = MaveDBFileSystem(base_url="https://example.test/api/v1")

    assert next_fs is not fs
    next_fs.close()


def test_client_uses_mavedb_api_key_header():
    client = MaveDBClient(base_url="https://example.test/api/v1", api_key="test-key")

    assert client.headers == {"X-API-key": "test-key"}
    assert client.has_api_key is True
    client.close()


def test_client_exists_falls_back_to_streaming_get_for_unsupported_head():
    requests = []

    def handler(request):
        requests.append(request.method)
        if request.method == "HEAD":
            return httpx.Response(405, request=request)
        return httpx.Response(200, content=b"large body", request=request)

    client = MaveDBClient(base_url="https://example.test/api/v1")
    client._session.close()
    client._session = httpx.Client(base_url="https://example.test/api/v1/", transport=httpx.MockTransport(handler))

    assert client.exists("score-sets/urn:mavedb:00000001-a-1/scores") is True
    assert requests == ["HEAD", "GET"]
    client.close()


def test_root_listing_only_includes_my_score_sets_with_api_key():
    public_fs = filesystem()
    private_fs = filesystem(api_key="test-key")

    assert public_fs.ls("mavedb://", detail=False) == ["score-sets"]
    assert private_fs.ls("mavedb://", detail=False) == ["score-sets", "my-score-sets"]


def test_score_set_listing():
    fs = filesystem()
    fs._score_set_file_exists = lambda urn, filename: False

    assert fs.ls("mavedb://score-sets/urn:mavedb:00000001-a-1", detail=False) == [
        "score-sets/urn:mavedb:00000001-a-1/scores.csv",
        "score-sets/urn:mavedb:00000001-a-1/counts.csv",
        "score-sets/urn:mavedb:00000001-a-1/variants.csv",
        "score-sets/urn:mavedb:00000001-a-1/metadata.json",
    ]


def test_score_sets_listing_uses_search_endpoint():
    fs = filesystem()
    requests = []

    def post_json(endpoint, payload):
        requests.append((endpoint, payload))
        return {
            "score_sets": [
                {
                    "urn": "urn:mavedb:00000001-a-1",
                    "experiment": {"title": "Experiment one"},
                    "title": "Score set one",
                },
                {"urn": "urn:mavedb:00000002-a-1", "title": "Score set two"},
            ],
            "num_score_sets": 10,
        }

    fs.client.post_json = post_json

    entries, total_count = fs.list_score_sets(limit=2, offset=4, query="BRCA1")

    assert requests == [
        (
            "score-sets/search",
            {
                "limit": 2,
                "offset": 4,
                "include_experiment_score_set_urns_and_count": False,
                "text": "BRCA1",
            },
        )
    ]
    assert total_count == 10
    assert entries == [
        {
            "name": "score-sets/urn:mavedb:00000001-a-1",
            "type": "directory",
            "size": 0,
            "display_name": "Experiment one (urn:mavedb:00000001-a-1)",
        },
        {
            "name": "score-sets/urn:mavedb:00000002-a-1",
            "type": "directory",
            "size": 0,
            "display_name": "Score set two (urn:mavedb:00000002-a-1)",
        },
    ]


def test_score_sets_listing_without_limit_fetches_one_default_api_page():
    fs = filesystem()
    requests = []

    def post_json(endpoint, payload):
        requests.append((endpoint, payload))
        return {
            "scoreSets": [
                {"urn": "urn:mavedb:00000003-a-1"},
                {"urn": "urn:mavedb:00000001-a-1"},
            ],
            "numScoreSets": 101,
        }

    fs.client.post_json = post_json

    entries, total_count = fs.list_score_sets()

    assert requests == [
        (
            "score-sets/search",
            {
                "limit": 100,
                "offset": 0,
                "include_experiment_score_set_urns_and_count": False,
            },
        ),
    ]
    assert total_count == 101
    assert entries == [
        {"name": "score-sets/urn:mavedb:00000003-a-1", "type": "directory", "size": 0},
        {"name": "score-sets/urn:mavedb:00000001-a-1", "type": "directory", "size": 0},
    ]


def test_score_sets_ls_uses_search_endpoint():
    fs = filesystem()
    fs.client.post_json = lambda endpoint, payload: {
        "scoreSets": [{"urn": "urn:mavedb:00000001-a-1"}],
        "numScoreSets": 1,
    }

    assert fs.ls("mavedb://score-sets", detail=False, limit=25, offset=0) == [
        "score-sets/urn:mavedb:00000001-a-1"
    ]


def test_my_score_sets_listing_uses_authenticated_search_endpoint():
    fs = filesystem(api_key="test-key")
    requests = []

    def post_json(endpoint, payload):
        requests.append((endpoint, payload))
        return {
            "scoreSets": [{"urn": "urn:mavedb:00000001-a-1", "title": "Private score set"}],
            "numScoreSets": 1,
        }

    fs.client.post_json = post_json

    entries, total_count = fs.list_score_sets(collection="my-score-sets", limit=25, offset=0)

    assert requests == [
        (
            "me/score-sets/search",
            {
                "limit": 25,
                "offset": 0,
                "include_experiment_score_set_urns_and_count": False,
            },
        )
    ]
    assert total_count == 1
    assert entries == [
        {
            "name": "my-score-sets/urn:mavedb:00000001-a-1",
            "type": "directory",
            "size": 0,
            "display_name": "Private score set (urn:mavedb:00000001-a-1)",
        }
    ]


def test_my_score_sets_listing_requires_api_key():
    fs = filesystem()

    with pytest.raises(PermissionError, match="API key"):
        fs.list_score_sets(collection="my-score-sets", limit=25, offset=0)


def test_my_score_set_file_listing_uses_my_score_sets_paths():
    fs = filesystem(api_key="test-key")
    fs._score_set_file_exists = lambda urn, filename: False

    assert fs.ls("mavedb://my-score-sets/urn:mavedb:00000001-a-1", detail=False) == [
        "my-score-sets/urn:mavedb:00000001-a-1/scores.csv",
        "my-score-sets/urn:mavedb:00000001-a-1/counts.csv",
        "my-score-sets/urn:mavedb:00000001-a-1/variants.csv",
        "my-score-sets/urn:mavedb:00000001-a-1/metadata.json",
    ]


def test_score_set_listing_includes_mapped_variants_when_available():
    fs = filesystem()
    fs._score_set_file_exists = lambda urn, filename: filename == "mapped-variants.json"

    assert fs.ls("mavedb://score-sets/urn:mavedb:00000001-a-1", detail=False) == [
        "score-sets/urn:mavedb:00000001-a-1/scores.csv",
        "score-sets/urn:mavedb:00000001-a-1/counts.csv",
        "score-sets/urn:mavedb:00000001-a-1/variants.csv",
        "score-sets/urn:mavedb:00000001-a-1/metadata.json",
        "score-sets/urn:mavedb:00000001-a-1/mapped-variants.json",
    ]


def test_json_files_escape_html_like_content():
    fs = filesystem()
    fs.client.get = lambda endpoint: response(
        b'{"methodText": "See <a href=\\"https://example.test?a=1&b=2\\">paper</a>"}'
    )

    data = fs.cat_file("mavedb://score-sets/urn:mavedb:00000001-a-1/metadata.json")

    assert b"<a " not in data
    assert b"</a>" not in data
    assert b"&" not in data
    assert b"\\u003ca href=" in data
    assert b"\\u003c/a\\u003e" in data
    assert b"\\u0026b=2" in data


def test_file_info_uses_content_length_for_json_files():
    fs = filesystem()
    fs.client.head = lambda endpoint: response(headers={"Content-Length": "123"})

    assert fs.info("mavedb://score-sets/urn:mavedb:00000001-a-1/metadata.json") == {
        "name": "score-sets/urn:mavedb:00000001-a-1/metadata.json",
        "type": "file",
        "size": 123,
    }


def test_file_info_uses_unknown_size_for_csv_files():
    fs = filesystem()

    assert fs.info("mavedb://score-sets/urn:mavedb:00000001-a-1/scores.csv") == {
        "name": "score-sets/urn:mavedb:00000001-a-1/scores.csv",
        "type": "file",
        "size": -1,
    }


def test_read_caches_returned_file_size():
    fs = filesystem()
    fs.client.get = lambda endpoint: response(b'{"x": "<tag>"}', headers={"Content-Length": "14"})

    data = fs.cat_file("mavedb://score-sets/urn:mavedb:00000001-a-1/metadata.json")

    assert fs.info("mavedb://score-sets/urn:mavedb:00000001-a-1/metadata.json")["size"] == len(data)


def test_csv_files_do_not_escape_angle_brackets():
    fs = filesystem()
    fs.client.get = lambda endpoint: response(b"accession,score\nvariant,<1\n")

    data = fs.cat_file("mavedb://score-sets/urn:mavedb:00000001-a-1/scores.csv")

    assert data == b"accession,score\nvariant,<1\n"
