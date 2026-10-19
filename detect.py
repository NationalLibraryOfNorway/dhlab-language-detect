import csv
import sqlite3
from argparse import ArgumentParser
from pathlib import Path

import fasttext
import gielladetect as gd

parser = ArgumentParser(description="Detekter språk på avsnittene i en DH-lab-database")
parser.add_argument("db_path", type=Path, help="Sti til databasefil")
parser.add_argument(
    "output_dir", type=Path, help="Mappe til utdata", default="data/db_langs/"
)
parser.add_argument(
    "--model_path", type=Path, default=None, help="Sti til lokal Glotlid-fil"
)

args = parser.parse_args()
path = args.db_path
output_path = args.output_dir / (path.stem + ".csv")

if args.model_path:
    model_file = str(args.model_path)
else:
    from huggingface_hub import hf_hub_download

    model_file = hf_hub_download(repo_id="cis-lmu/glotlid", filename="model_v3.bin")

glotlid_model = fasttext.load_model(model_file)


def run_glotlid(text: str) -> tuple[str, float]:
    predictions = glotlid_model.predict(text)
    lang = str(predictions[0][0]).replace("__label__", "")
    # only fetch ISO code, not script
    lang = lang.split("_")[0]
    conf = round(predictions[1][0], 2)

    return (lang, conf)


with open(output_path, "w+") as f:
    csvwriter = csv.writer(f)
    csvwriter.writerow(
        [
            "dhlabid",
            "para_num",
            "glotlid_lang",
            "glotlid_conf",
            "gielladetect_lang",
            "len_para_text",
            "tokens_para_text",
        ]
    )

    with sqlite3.connect(path) as con:
        cur = con.cursor()

        cur.execute("SELECT urn FROM urns;")

        dhlabids = cur.fetchall()

        for dhlabid in dhlabids:
            cur.execute(
                "SELECT para, para_text FROM ft_para WHERE urn MATCH ?;", (dhlabid)
            )
            paras = cur.fetchall()

            for para_num, para_text in paras:
                gl_lang, gl_conf = run_glotlid(para_text)
                gd_lang = gd.detect(para_text)
                row = [
                    dhlabid[0],
                    para_num,
                    gl_lang,
                    gl_conf,
                    gd_lang,
                    len(para_text),
                    len(para_text.split()),
                ]
                csvwriter.writerow(row)
