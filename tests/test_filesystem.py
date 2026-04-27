from mavedb_fsspec import MaveDBFileSystem
from mavedb_fsspec.client import MaveDBClient


def test_filesystem_imports():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")

    assert fs.protocol == "mavedb"


def test_client_uses_mavedb_api_key_header():
    client = MaveDBClient(base_url="https://example.test/api/v1", api_key="test-key")

    assert client.headers == {"X-API-key": "test-key"}


def test_score_set_listing():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
    fs._score_set_file_exists = lambda urn, filename: False

    assert fs.ls("mavedb://score-sets/urn:mavedb:00000001-a-1", detail=False) == [
        "score-sets/urn:mavedb:00000001-a-1/scores.csv",
        "score-sets/urn:mavedb:00000001-a-1/counts.csv",
        "score-sets/urn:mavedb:00000001-a-1/variants.csv",
        "score-sets/urn:mavedb:00000001-a-1/metadata.json",
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
