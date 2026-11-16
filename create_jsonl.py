import sys
import json
import requests
import pandas as pd

sami_language_codes = ["sme", "sma", "smj", "smi", "sms", "smn"]
columns = ["title", "year", "names", "num_tokens", "num_paragraphs"] + [f"detected_{lang}_percentage" for lang in sami_language_codes] + ["all_detected_languages", "library_languages"]

tokens_mapper = {f"detected_{lang}_tokens": f"detected_{lang}_percentage" for lang in sami_language_codes}
tokens_mapper["all_detected_languages_tokens"] = "all_detected_languages"
paragraphs_mapper = {f"detected_{lang}_paragraphs": f"detected_{lang}_percentage" for lang in sami_language_codes}
paragraphs_mapper["all_detected_languages_paragraphs"] = "all_detected_languages"

data = []

for line in sys.stdin:
    book_dict = dict()

    json_line = json.loads(line)

    book_dict["dhlabid"] = json_line["dhlabid"]

    r = requests.get(f"https://api.nb.no/dhlab/id/{book_dict['dhlabid']}")
    book_dict["urn"] = r.json()["urn"]["0"]

    r2 = requests.get(f"https://api.nb.no/catalog/v1/items/{book_dict['urn']}?fields=metadata")

    metadata = r2.json().get("metadata")

    book_dict["title"] = metadata.get("title")

    book_dict["year"] = metadata.get("originInfo").get("issued")

    book_dict["library_languages"] = [x["code"] for x in metadata.get("languages")]

    book_dict["names"] = [x["name"] for x in metadata.get("people")]

    book_dict["all_detected_languages_tokens"] = json_line["language_statistics_tokens"]
    book_dict["all_detected_languages_paragraphs"] = json_line["language_statistics_paragraphs"]
    #detected_languages_paragraphs = json_line["language_statistics_paragraphs"]

    for lang in sami_language_codes:
        book_dict[f"detected_{lang}_tokens"] = book_dict["all_detected_languages_tokens"].get(lang, 0.0)
        book_dict[f"detected_{lang}_paragraphs"] = book_dict["all_detected_languages_paragraphs"].get(lang, 0.0)

    book_dict["num_tokens"] = json_line["num_tokens"]
    book_dict["num_paragraphs"] = json_line["num_paragraphs"]

    data.append(book_dict)

df = pd.DataFrame(data)

tokens_df = df.rename(columns=tokens_mapper)
tokens_df[columns].to_json("tokens_output.jsonl", lines=True, orient="records", index=False)
paragraphs_df = df.rename(columns=paragraphs_mapper)
paragraphs_df[columns].to_json("paragraphs_output.jsonl", lines=True, orient="records", index=False)





    