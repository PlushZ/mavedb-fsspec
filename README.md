# mavedb-fsspec

`mavedb-fsspec` is a read-only [fsspec](https://filesystem-spec.readthedocs.io/) filesystem adapter for [MaveDB](https://mavedb.org/).
It exposes MaveDB score set data as filesystem-like paths so Python tools that understand fsspec can browse and read MaveDB data without using MaveDB API endpoints directly.

## What is fsspec?

`fsspec` is a Python interface for working with many storage systems through a common filesystem API. Code can use familiar operations such as `ls`, `info`, `open`, and `cat` against local files, HTTP resources, cloud buckets, and custom filesystems.

`mavedb-fsspec` registers the `mavedb://` protocol with fsspec. This lets code access MaveDB data like:

```text
mavedb://score-sets/urn:mavedb:00000670-a-1/scores.csv
```

instead of manually constructing API requests.

## Installation

Install from PyPI:

```bash
pip install mavedb-fsspec
```

Or with uv:

```bash
uv add mavedb-fsspec
```

`fsspec` and the other runtime dependencies are installed automatically.

## Filesystem layout

The filesystem currently exposes score set data:

```text
mavedb://
  score-sets/
    {urn}/
      scores.csv
      counts.csv
      variants.csv
      metadata.json
      mapped-variants.json
  my-score-sets/
    {urn}/
      scores.csv
      counts.csv
      variants.csv
      metadata.json
      mapped-variants.json
```

`score-sets/` lists public published score sets using the MaveDB search API.

`my-score-sets/` is only available when an API key is provided. It lists score sets associated with the authenticated MaveDB user.

`mapped-variants.json` is only listed for a score set when MaveDB has mapped variants for that score set.

## Basic usage

```python
import fsspec

fs = fsspec.filesystem("mavedb")

print(fs.ls("mavedb://", detail=False))
print(fs.ls("mavedb://score-sets", detail=False, limit=25, offset=0))

data = fs.cat("mavedb://score-sets/urn:mavedb:00000670-a-1/scores.csv")
print(data[:500].decode())
```

The filesystem class can also be instantiated directly:

```python
from mavedb_fsspec import MaveDBFileSystem

fs = MaveDBFileSystem()
print(fs.ls("score-sets", detail=False, limit=25))
```

## Authenticated usage

Use an API key to access `my-score-sets/` and private score set files that your MaveDB account can read:

```python
import fsspec

fs = fsspec.filesystem("mavedb", api_key="YOUR_MAVEDB_API_KEY")

print(fs.ls("mavedb://", detail=False))
print(fs.ls("mavedb://my-score-sets", detail=False, limit=25, offset=0))
```

## Reading with file-like objects

`mavedb-fsspec` supports fsspec's file-like API:

```python
import fsspec

with fsspec.open("mavedb://score-sets/urn:mavedb:00000670-a-1/metadata.json", "rb") as handle:
    metadata = handle.read()
```

Files are currently downloaded completely into memory when opened. Similarly, `cat_file()` downloads the complete
file before applying `start` and `end` slicing; these operations do not issue HTTP range requests.

## Configuration

The public MaveDB API is used by default:

```python
fs = fsspec.filesystem("mavedb")
```

Advanced options:

```python
fs = fsspec.filesystem(
    "mavedb",
    base_url="https://api.mavedb.org/api/v1",
    api_key="YOUR_MAVEDB_API_KEY",
    timeout=30.0,
)
```

## Development

Install this repository in editable mode with the development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run tests with:

```bash
python -m pytest
```

Run Ruff with:

```bash
python -m ruff check .
```

## Notes

This filesystem is read-only. It does not upload data to MaveDB.

File information uses `-1` when the size is unknown. MaveDB endpoints can return `405 Method Not Allowed` for
`HEAD` requests, so a size may remain unknown until the file has been read.

The JSON files returned by this adapter escape literal `<`, `>`, and `&` characters. This keeps JSON safe for
consumers that reject HTML-like content during upload, while preserving equivalent JSON string values.

## License

MIT. See [LICENSE](LICENSE).
