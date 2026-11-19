import concurrent.futures
import functools
import itertools
import json
import threading
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util import Retry

from language_statistics_per_text import sami_language_codes

columns_for_delivery = (
    [
        "title",
        "year",
        "names",
    ]
    + [f"detected_{lang}_share" for lang in sami_language_codes]
    + [
        "all_detected_languages",
        "library_languages",
        "num_tokens",
        "num_paragraphs",
        "urn",
        "dhlabid",
    ]
)


REQUEST_TIMEOUT = 30

# Number of decimals for language shares in the delivery files
SHARE_DECIMALS = 4

# Transient errors (rate limiting, server errors, connection problems) are
# retried with exponential backoff. 404 is not retried: it means the id
# does not exist, and is handled as a normal outcome.
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    respect_retry_after_header=True,
)

_thread_local = threading.local()


def get_session() -> requests.Session:
    """One session per worker thread, since requests.Session is not guaranteed to be thread-safe"""
    if not hasattr(_thread_local, "session"):
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        _thread_local.session = session
    return _thread_local.session


@functools.cache
def fetch_urn(dhlabid: str) -> str | None:
    """Fetch urn for a dhlabid from the API. Returns None if the dhlabid is not found (404).

    Cached so the same book is only looked up once per process. Other errors
    are raised after retries, and functools.cache does not cache exceptions,
    so failed lookups are tried again on the next call.
    """
    r = get_session().get(
        f"https://api.nb.no/dhlab/id/{dhlabid}", timeout=REQUEST_TIMEOUT
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()["urn"]["0"]


@functools.cache
def fetch_metadata(urn: str) -> dict | None:
    """Fetch the delivery fields from nb.no/items metadata. Returns None if the urn is not found (404).

    Cached and raises on other errors, like fetch_urn. Only the parsed
    fields are cached, not the full API response, to keep memory use low.
    """
    r = get_session().get(
        f"https://api.nb.no/catalog/v1/items/{urn}?fields=metadata",
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return parse_metadata(r.json().get("metadata") or {})


def parse_metadata(nb_metadata: dict) -> dict:
    """Pick out the delivery fields from nb.no/items metadata"""
    return {
        "title": nb_metadata.get("title"),
        "year": (nb_metadata.get("originInfo") or {}).get("issued"),
        "library_languages": [x["code"] for x in nb_metadata.get("languages") or []],
        "names": [x.get("name") for x in nb_metadata.get("people", []) if "name" in x],
    }


def has_enough_sami_paragraphs(
    paragraph_statistics: dict[str, float], min_sami_paragraph_share: float
) -> bool:
    """Check if at least one Sámi language has a paragraph share at or above the threshold"""
    return any(
        paragraph_statistics.get(lang, 0.0) >= min_sami_paragraph_share
        for lang in sami_language_codes
    )


def make_delivery_record(
    json_line: dict, urn: str, metadata: dict, statistic: str
) -> dict:
    """Build one delivery record, using either the "tokens" or the "paragraphs" language statistics.

    The token and paragraph files share the same columns (columns_for_delivery).
    """
    language_statistics = {
        lang: round(share, SHARE_DECIMALS)
        for lang, share in json_line[f"language_statistics_{statistic}"].items()
    }
    record = {
        **metadata,
        **{
            f"detected_{lang}_share": language_statistics.get(lang, 0.0)
            for lang in sami_language_codes
        },
        "urn": urn,
        "dhlabid": json_line["dhlabid"],
        "all_detected_languages": language_statistics,
        "num_tokens": json_line["num_tokens"],
        "num_paragraphs": json_line["num_paragraphs"],
    }
    return {column: record[column] for column in columns_for_delivery}


def process_book(json_line: dict) -> tuple[tuple[dict, dict] | None, bool]:
    """Look up urn and metadata for one book.

    Returns (records, failed). records is the (tokens, paragraphs) delivery
    records, or None if the book is dropped because the urn or metadata is
    missing. failed is True if a lookup failed for another reason than 404,
    in which case a warning is printed.
    """
    dhlabid = json_line["dhlabid"]

    try:
        urn = fetch_urn(dhlabid)
        metadata = fetch_metadata(urn) if urn is not None else None
    except requests.RequestException as e:
        print(f"Warning: lookup failed for dhlabid {dhlabid}: {e!r}")
        return None, True

    if metadata is None:  # urn or metadata not found (404)
        return None, False

    records = (
        make_delivery_record(json_line, urn, metadata, "tokens"),
        make_delivery_record(json_line, urn, metadata, "paragraphs"),
    )
    return records, False


def make_files_for_delivery(
    in_file: Path,
    out_dir: Path,
    min_sami_paragraph_share: float = 0.0,
    max_workers: int = 8,
    batch_size: int = 1000,
) -> None:
    """Fetch nb metadata and add Sámi language statistics as columns separate from the other languages detected.
    Make separate files for language statistics based on % of tokens and % of paragraphs. The files share the same columns

    Books are only kept if at least one Sámi language makes up at least
    `min_sami_paragraph_share` (a fraction between 0 and 1) of the paragraphs,
    and both the urn and the nb.no metadata can be found.
    """
    num_kept = 0
    num_skipped = 0
    num_not_found = 0
    failed_dhlabids = []

    with (
        in_file.open() as in_f,
        (out_dir / "tokens_stats.jsonl").open("w") as tokens_f,
        (out_dir / "paragraphs_stats.jsonl").open("w") as paragraphs_f,
        concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor,
    ):
        for lines in itertools.batched(tqdm(in_f, unit=" lines"), batch_size):
            json_lines = [json.loads(line) for line in lines]
            books = [
                json_line
                for json_line in json_lines
                if has_enough_sami_paragraphs(
                    json_line["language_statistics_paragraphs"],
                    min_sami_paragraph_share,
                )
            ]
            num_skipped += len(json_lines) - len(books)

            for json_line, (records, failed) in zip(
                books, executor.map(process_book, books)
            ):
                if failed:
                    failed_dhlabids.append(json_line["dhlabid"])
                if records is None:
                    if not failed:
                        num_not_found += 1
                    continue
                tokens_record, paragraphs_record = records
                tokens_f.write(json.dumps(tokens_record) + "\n")
                paragraphs_f.write(json.dumps(paragraphs_record) + "\n")
                num_kept += 1

    print(
        f"Kept {num_kept} books, skipped {num_skipped} with Sámi paragraph share "
        f"below {min_sami_paragraph_share}, {num_not_found} with urn or metadata "
        f"not found (404)"
    )
    if failed_dhlabids:
        print(
            f"Warning: {len(failed_dhlabids)} lookups failed after retries, "
            f"rerun to try them again. dhlabids: {failed_dhlabids}"
        )


if __name__ == "__main__":
    delivery_out_dir = Path("data/sámi_language_statistics/")
    min_sami_paragraph_share = 0.1
    max_workers = 8

    gielladetect_statistics_file = Path("data/language_statistics_gielladetect.jsonl")
    assert gielladetect_statistics_file.exists()

    print("Making gielladetect delivery files")
    gielladetect_out_dir = delivery_out_dir / "gielladetect/"
    gielladetect_out_dir.mkdir(exist_ok=True, parents=True)
    make_files_for_delivery(
        gielladetect_statistics_file,
        gielladetect_out_dir,
        min_sami_paragraph_share,
        max_workers,
    )

    glotlid_statistics_file = Path("data/language_statistics_glotlid.jsonl")
    assert glotlid_statistics_file.exists()

    print("Making glotlid delivery files")
    glotlid_out_dir = delivery_out_dir / "glotlid/"
    glotlid_out_dir.mkdir(exist_ok=True, parents=True)
    make_files_for_delivery(
        glotlid_statistics_file, glotlid_out_dir, min_sami_paragraph_share, max_workers
    )
