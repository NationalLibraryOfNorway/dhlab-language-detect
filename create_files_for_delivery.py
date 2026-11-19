import json
from pathlib import Path

import pandas as pd
import requests

from language_statistics_per_text import sami_language_codes

columns_for_delivery = (
    [
        "title",
        "year",
        "names",
    ]
    + [f"detected_{lang}_share" for lang in sami_language_codes]
    + [
        "urn",
        "dhlabid",
        "all_detected_languages",
        "library_languages",
        "num_tokens",
        "num_paragraphs",
    ]
)


def get_urn(dhlabid: str) -> str | None:
    """Get urn from dhlabid"""
    try:
        r = requests.get(f"https://api.nb.no/dhlab/id/{dhlabid}", timeout=30)
        r.raise_for_status()
        return r.json()["urn"]["0"]
    except requests.RequestException as e:
        print(f"Warning: could not get urn for dhlabid {dhlabid}: {e!r}")


def get_metadata(urn: str) -> dict:
    """Add selected fields from nb.no/items metadata.

    If the lookup fails, a warning is printed and the fields are set to None,
    so a single bad id does not stop the whole run.
    """
    metadata_dict = {
        "title": None,
        "year": None,
        "library_languages": None,
        "names": None,
    }

    try:
        r2 = requests.get(
            f"https://api.nb.no/catalog/v1/items/{urn}?fields=metadata", timeout=30
        )
        r2.raise_for_status()
        nb_metadata = r2.json().get("metadata") or {}

        metadata_dict["title"] = nb_metadata.get("title")
        metadata_dict["year"] = (nb_metadata.get("originInfo") or {}).get("issued")
        metadata_dict["library_languages"] = [
            x["code"] for x in nb_metadata.get("languages") or []
        ]
        metadata_dict["names"] = [
            x.get("name") for x in nb_metadata.get("people", []) if "name" in x
        ]
    except requests.RequestException as e:
        print(f"Warning: could not get metadata for urn {urn}: {e!r}")

    return metadata_dict


def save_token_statistics_only(df: pd.DataFrame, out_file: Path) -> None:
    """Rename token-specific statistics columns to the general statistics column names and save"""
    token_statistics_column_mapper = {
        f"detected_{lang}_tokens": f"detected_{lang}_share"
        for lang in sami_language_codes
    }
    token_statistics_column_mapper["all_detected_languages_tokens"] = (
        "all_detected_languages"
    )
    df = df.rename(columns=token_statistics_column_mapper)
    df[columns_for_delivery].to_json(
        out_file, lines=True, orient="records", index=False
    )


def save_paragraphs_statistics_only(df: pd.DataFrame, out_file: Path) -> None:
    """Rename paragraph-specific statistics columns to the general statistics column names and save"""
    paragraph_statistics_column_mapper = {
        f"detected_{lang}_paragraphs": f"detected_{lang}_share"
        for lang in sami_language_codes
    }
    paragraph_statistics_column_mapper["all_detected_languages_paragraphs"] = (
        "all_detected_languages"
    )

    paragraphs_df = df.rename(columns=paragraph_statistics_column_mapper)
    paragraphs_df[columns_for_delivery].to_json(
        out_file, lines=True, orient="records", index=False
    )


def has_enough_sami_paragraphs(
    paragraph_statistics: dict[str, float], min_sami_paragraph_share: float
) -> bool:
    """Check if at least one Sámi language has a paragraph share at or above the threshold"""
    return any(
        paragraph_statistics.get(lang, 0.0) >= min_sami_paragraph_share
        for lang in sami_language_codes
    )


def make_files_for_delivery(
    in_file: Path, out_dir: Path, min_sami_paragraph_share: float = 0.0
) -> None:
    """Fetch nb metadata and add Sámi language statistics as columns separate from the other languages detected.
    Make separate files for language statistics based on % of tokens and % of paragraphs. The files share the same columns

    Books are only kept if at least one Sámi language makes up at least
    `min_sami_paragraph_share` (a fraction between 0 and 1) of the paragraphs.
    """

    data = []
    num_skipped = 0

    for line in in_file.open():
        json_line = json.loads(line)

        urn = get_urn(json_line["dhlabid"])
        if urn is None:
            continue

        if not has_enough_sami_paragraphs(
            json_line["language_statistics_paragraphs"], min_sami_paragraph_share
        ):
            num_skipped += 1
            continue

        book_dict = {}

        book_dict["dhlabid"] = json_line["dhlabid"]
        book_dict["urn"] = urn

        book_dict["all_detected_languages_tokens"] = json_line[
            "language_statistics_tokens"
        ]
        book_dict["all_detected_languages_paragraphs"] = json_line[
            "language_statistics_paragraphs"
        ]

        for lang in sami_language_codes:
            book_dict[f"detected_{lang}_tokens"] = book_dict[
                "all_detected_languages_tokens"
            ].get(lang, 0.0)
            book_dict[f"detected_{lang}_paragraphs"] = book_dict[
                "all_detected_languages_paragraphs"
            ].get(lang, 0.0)

        book_dict["num_tokens"] = json_line["num_tokens"]
        book_dict["num_paragraphs"] = json_line["num_paragraphs"]

        book_dict.update(get_metadata(urn=book_dict["urn"]))

        data.append(book_dict)

    print(
        f"Kept {len(data)} books, skipped {num_skipped} with Sámi paragraph share "
        f"below {min_sami_paragraph_share}"
    )

    df = pd.DataFrame(data)

    save_token_statistics_only(df, out_file=out_dir / "tokens_stats.jsonl")
    save_paragraphs_statistics_only(df, out_file=out_dir / "paragraphs_stats.jsonl")


if __name__ == "__main__":
    delivery_out_dir = Path("data/sámi_language_statistics/")
    min_sami_paragraph_share = 0.1

    gielladetect_statistics_file = Path("data/language_statistics_gielladetect.jsonl")
    assert gielladetect_statistics_file.exists()

    print("Making gielladetect delivery files")
    gielladetect_out_dir = delivery_out_dir / "gielladetect/"
    gielladetect_out_dir.mkdir(exist_ok=True, parents=True)
    make_files_for_delivery(
        gielladetect_statistics_file, gielladetect_out_dir, min_sami_paragraph_share
    )

    glotlid_statistics_file = Path("data/language_statistics_glotlid.jsonl")
    assert glotlid_statistics_file.exists()

    print("Making glotlid delivery files")
    glotlid_out_dir = delivery_out_dir / "glotlid/"
    glotlid_out_dir.mkdir(exist_ok=True, parents=True)
    make_files_for_delivery(
        glotlid_statistics_file, glotlid_out_dir, min_sami_paragraph_share
    )
