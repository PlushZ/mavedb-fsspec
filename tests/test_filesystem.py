from mavedb_fsspec import MaveDBFileSystem
from mavedb_fsspec.client import MaveDBClient


def test_filesystem_imports():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")

    assert fs.protocol == "mavedb"


def test_client_uses_mavedb_api_key_header():
    client = MaveDBClient(base_url="https://example.test/api/v1", api_key="test-key")

    assert client.headers == {"X-API-key": "test-key"}
    assert client.has_api_key is True


def test_root_listing_only_includes_my_score_sets_with_api_key():
    public_fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
    private_fs = MaveDBFileSystem(base_url="https://example.test/api/v1", api_key="test-key")

    assert public_fs.ls("mavedb://", detail=False) == ["score-sets"]
    assert private_fs.ls("mavedb://", detail=False) == ["score-sets", "my-score-sets"]


def test_score_set_listing():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
    fs._score_set_file_exists = lambda urn, filename: False

    assert fs.ls("mavedb://score-sets/urn:mavedb:00000001-a-1", detail=False) == [
        "score-sets/urn:mavedb:00000001-a-1/scores.csv",
        "score-sets/urn:mavedb:00000001-a-1/counts.csv",
        "score-sets/urn:mavedb:00000001-a-1/variants.csv",
        "score-sets/urn:mavedb:00000001-a-1/metadata.json",
    ]


def test_score_sets_listing_uses_search_endpoint():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
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
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
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
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
    fs.client.post_json = lambda endpoint, payload: {
        "scoreSets": [{"urn": "urn:mavedb:00000001-a-1"}],
        "numScoreSets": 1,
    }

    assert fs.ls("mavedb://score-sets", detail=False, limit=25, offset=0) == [
        "score-sets/urn:mavedb:00000001-a-1"
    ]


def test_my_score_sets_listing_uses_authenticated_search_endpoint():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1", api_key="test-key")
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
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")

    try:
        fs.list_score_sets(collection="my-score-sets", limit=25, offset=0)
    except PermissionError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("Expected PermissionError")


def test_my_score_set_file_listing_uses_my_score_sets_paths():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1", api_key="test-key")
    fs._score_set_file_exists = lambda urn, filename: False

    assert fs.ls("mavedb://my-score-sets/urn:mavedb:00000001-a-1", detail=False) == [
        "my-score-sets/urn:mavedb:00000001-a-1/scores.csv",
        "my-score-sets/urn:mavedb:00000001-a-1/counts.csv",
        "my-score-sets/urn:mavedb:00000001-a-1/variants.csv",
        "my-score-sets/urn:mavedb:00000001-a-1/metadata.json",
    ]


def test_score_set_listing_includes_mapped_variants_when_available():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
    fs._score_set_file_exists = lambda urn, filename: filename == "mapped-variants.json"

    assert fs.ls("mavedb://score-sets/urn:mavedb:00000001-a-1", detail=False) == [
        "score-sets/urn:mavedb:00000001-a-1/scores.csv",
        "score-sets/urn:mavedb:00000001-a-1/counts.csv",
        "score-sets/urn:mavedb:00000001-a-1/variants.csv",
        "score-sets/urn:mavedb:00000001-a-1/metadata.json",
        "score-sets/urn:mavedb:00000001-a-1/mapped-variants.json",
    ]


def test_json_files_escape_html_like_content():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
    fs.client.get_bytes = lambda endpoint: b'{"methodText": "See <a href=\\"https://example.test\\">paper</a>"}'

    data = fs.cat_file("mavedb://score-sets/urn:mavedb:00000001-a-1/metadata.json")

    assert b"<a " not in data
    assert b"</a>" not in data
    assert b"\\u003ca href=" in data
    assert b"\\u003c/a\\u003e" in data


def test_csv_files_do_not_escape_angle_brackets():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
    fs.client.get_bytes = lambda endpoint: b"accession,score\nvariant,<1\n"

    data = fs.cat_file("mavedb://score-sets/urn:mavedb:00000001-a-1/scores.csv")

    assert data == b"accession,score\nvariant,<1\n"
