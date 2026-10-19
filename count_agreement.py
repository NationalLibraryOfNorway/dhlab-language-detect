import concurrent.futures
from pathlib import Path

import pandas as pd
from tqdm import tqdm


def agreement_per_size(csv_file: Path, size_column: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    df["agreement"] = df.gielladetect_lang == df.glotlid_lang
    agreement_df = pd.DataFrame(
        {
            "num_paragraphs": len(df_),
            "agreeing_paragraphs": df_["agreement"].sum(),
            "size": size,
            "size_column": size_column,
        }
        for size, df_ in df.groupby(size_column)
    )
    return agreement_df


def make_agreement_dataframe_across_csvs(
    csvs: list[Path], max_workers: int, size_column: str, output_file: Path
):
    agreement_dfs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                agreement_per_size, csv_file=csv_file, size_column=size_column
            )
            for csv_file in csvs
        ]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(csvs)):
            agreement_dfs.append(future.result())

    agreement_df = pd.concat(agreement_dfs)
    agreement_df = pd.DataFrame(
        {
            "size": size,
            "agreeing_paragraphs": df_.agreeing_paragraphs.sum(),
            "num_paragraphs": df_.num_paragraphs.sum(),
            "size_column": size_column,
        }
        for size, df_ in agreement_df.groupby("size")
    )
    agreement_df.sort_values("size").to_csv(output_file, index=False)


if __name__ == "__main__":
    # juster avhengig av datamaskin
    max_workers = 8

    data_dir = Path(__file__).parent / "data"

    csvs = list((data_dir / "db_langs/").glob("*.csv"))

    size_columns = ["len_para_text", "tokens_para_text"]
    for size_column in size_columns:
        make_agreement_dataframe_across_csvs(
            csvs=csvs,
            max_workers=max_workers,
            size_column=size_column,
            output_file=data_dir / f"language_agreement_{size_column}.csv",
        )
