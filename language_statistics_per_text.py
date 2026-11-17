import concurrent.futures
from pathlib import Path

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


def count_detected_languages(csv_file: Path, lang_column: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)

    # filter out too short and too long paragraphs (see plot_agreement.ipynb)
    df = df[(df.tokens_para_text >= 10) & (df.tokens_para_text <= 600)]

    # filter out texts with no Sámi language paragraphs
    df = df.groupby(by="dhlabid").filter(
        lambda df_: any(
            x in df_[lang_column].unique()
            for x in ["sme", "sma", "smj", "smi", "sms", "smn"]
        )
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
        for dhlabid, df_ in tqdm(df.groupby("dhlabid"), total=df.dhlabid.nunique())
    )


def make_language_statistics_across_csvs(
    csvs: list[Path], max_workers: int, lang_column: str, output_file: Path
):
    dfs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                count_detected_languages, csv_file=csv_file, lang_column=lang_column
            )
            for csv_file in csvs
        ]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(csvs)):
            dfs.append(future.result())

    df = pd.concat(dfs).to_json(output_file, index=False, lines=True, orient="records")
    df.to_json(output_file, lines=True, orient="records")


if __name__ == "__main__":
    # juster avhengig av datamaskin
    max_workers = 8

    data_dir = Path(__file__).parent / "data"

    csvs = list((data_dir / "db_langs/").glob("*.csv"))

    lang_columns = ["glotlid_lang", "gielladetect_lang"]
    for lang_column in lang_columns:
        make_language_statistics_across_csvs(
            csvs=csvs,
            max_workers=max_workers,
            lang_column=lang_column,
            output_file=data_dir / f"language_statistics_{lang_column}.jsonl",
        )
