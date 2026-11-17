import concurrent.futures
from pathlib import Path
from typing import TextIO

import pandas as pd
from tqdm import tqdm


def language_percentages_tokens(df: pd.DataFrame, lang_column: str) -> dict[str, float]:
    """Make a dict of {langcode: % of tokens in this language} (after filter)"""
    total_freq = df.sum()["tokens_para_text"]
    languages = df.groupby(lang_column).sum()["tokens_para_text"] / total_freq
    return languages.to_dict()


def language_percentages_paragraphs(
    df: pd.DataFrame, lang_column: str
) -> dict[str, float]:
    """Make a dict of {langcode: % of paragraphs in this language} (after filter)"""

    total_paragraphs = len(df)
    languages = df.groupby(lang_column).count() / total_paragraphs
    return languages.to_dict()["dhlabid"]


sami_language_codes = ["sme", "sma", "smj", "smi", "sms", "smn"]


def statistics_per_text(df: pd.DataFrame, lang_column: str) -> pd.DataFrame:
    """Make one row of language statistics per text, using the given lang column"""

    # filter out texts with no Sámi language paragraphs
    df = df.groupby(by="dhlabid").filter(
        lambda df_: df_[lang_column].isin(sami_language_codes).any()
    )

    return pd.DataFrame(
        {
            "dhlabid": dhlabid,
            "num_tokens": df_.sum()["tokens_para_text"],
            "num_paragraphs": len(df_),
            "language_statistics_tokens": language_percentages_tokens(df_, lang_column),
            "language_statistics_paragraphs": language_percentages_paragraphs(
                df_, lang_column
            ),
        }
        for dhlabid, df_ in df.groupby("dhlabid")
    )


def count_detected_languages(
    csv_file: Path, glotlid_column: str, gielladetect_column: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the csv once and return the statistics dataframes for
    (glotlid, gielladetect)"""
    df = pd.read_csv(csv_file)

    # filter out too short and too long paragraphs (see plot_agreement.ipynb)
    df = df[(df.tokens_para_text >= 10) & (df.tokens_para_text <= 600)]

    return (
        statistics_per_text(df, glotlid_column),
        statistics_per_text(df, gielladetect_column),
    )


def write_jsonl(df: pd.DataFrame, f: TextIO):
    if df.empty:
        return
    f.write(df.to_json(orient="records", lines=True, force_ascii=False))
    f.flush()


def make_language_statistics_across_csvs(
    csvs: list[Path],
    max_workers: int,
    glotlid_column: str,
    gielladetect_column: str,
    glotlid_output_file: Path,
    gielladetect_output_file: Path,
):
    with (
        concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor,
        glotlid_output_file.open("w", encoding="utf-8") as glotlid_f,
        gielladetect_output_file.open("w", encoding="utf-8") as gielladetect_f,
    ):
        futures = [
            executor.submit(
                count_detected_languages,
                csv_file=csv_file,
                glotlid_column=glotlid_column,
                gielladetect_column=gielladetect_column,
            )
            for csv_file in csvs
        ]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(csvs)):
            glotlid_df, gielladetect_df = future.result()
            write_jsonl(glotlid_df, glotlid_f)
            write_jsonl(gielladetect_df, gielladetect_f)


if __name__ == "__main__":
    # juster avhengig av datamaskin
    max_workers = 8

    data_dir = Path(__file__).parent / "data"

    csvs = list((data_dir / "db_langs/").glob("*.csv"))

    glotlid_column = "glotlid_lang"
    gielladetect_column = "gielladetect_lang"
    make_language_statistics_across_csvs(
        csvs=csvs,
        max_workers=max_workers,
        glotlid_column=glotlid_column,
        gielladetect_column=gielladetect_column,
        glotlid_output_file=data_dir / "language_statistics_glotlid.jsonl",
        gielladetect_output_file=data_dir / "language_statistics_gielladetect.jsonl",
    )
