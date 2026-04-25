from mavedb_fsspec import MaveDBFileSystem


def test_filesystem_imports():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")

    assert fs.protocol == "mavedb"


def test_score_set_listing():
    fs = MaveDBFileSystem(base_url="https://example.test/api/v1")
    available_files = {"scores.csv", "variants.csv", "metadata.json"}
    fs._score_set_file_exists = lambda urn, filename: filename in available_files

    assert fs.ls("mavedb://score-sets/urn:mavedb:00000001-a-1", detail=False) == [
        "score-sets/urn:mavedb:00000001-a-1/scores.csv",
        "score-sets/urn:mavedb:00000001-a-1/variants.csv",
        "score-sets/urn:mavedb:00000001-a-1/metadata.json",
    ]
