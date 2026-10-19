import concurrent.futures
from pathlib import Path

import pandas as pd
from tqdm import tqdm


def count_short_paragraphs(csv_file: Path, min_str_len: int) -> tuple[int, int]:
    df = pd.read_csv(csv_file)
    return len(df), (df["len_para_text"] < min_str_len).sum()


if __name__ == "__main__":
    # snittlengden på et ord er 4-5 bokstaver
    min_str_len = 5

    # juster avhengig av datamaskin
    max_workers = 8

    csvs = list((Path(__file__).parent / "data/db_langs/").glob("*.csv"))

    short_paragraphs = 0
    total_paragraphs = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(count_short_paragraphs, csv_file, min_str_len)
            for csv_file in csvs
        ]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(csvs)):
            paras, short_paras = future.result()
            short_paragraphs += short_paras
            total_paragraphs += paras

    print(
        f"{short_paragraphs} av {total_paragraphs} har str.len mindre enn {min_str_len}"
    )
