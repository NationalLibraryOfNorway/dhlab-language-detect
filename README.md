
# Språkdeteksjon og analyse av språk på avsnittsnivå i DH-lab-databaser

Dette repoet inneholder skript for å kjøre språkdeteksjon på alle avsnitt i DH-labens databaser og analysere resultatet av dette.

## Oppsett
Vi bruker python og pdm. 
Innstaller avhengigheter med `pdm install` 

## Kodeoversikt

### Språkdeteksjon
Bruk `detect.py` for å detektere språket i hvert avsnitt i en databasefil fra dhlab.
Vi bruker både gielladetect og glotlid.

Kjør skriptet i parallell, ved å bruke GNU parallel:

```bash
ls /data/db/ft/alto_1* | parallel -j4 "pdm run detect.py {} out"
```

Du kan laste ned HF-modellen for glotlid separat fra skriptkjøring slik (for Docker):
```bash
mkdir models
pdm run hf download cis-lmu/glotlid model_v3.bin --local-dir ./models
```

### Enighet mellom språkdeteksjon-modellene
Skriptet `count_agreement.py` teller hvor mange avsnitt gielladetect og glotlid er enige om språket, gruppert på avsnittslengde. Resultatet skrives til `data/language_agreement_len_para_text.csv` og `data/language_agreement_tokens_para_text.csv`. Skriptet fordrer at språkdeteksjonen har kjørt og at filene ligger på `data/db_langs/` (relativt til rota i denne mappa). 

I notebooken `notebooks/plot_agreement.ipynb` leser vi outputfilene fra `count_agreement.py`. Vi ser på hvordan lengden av avsnittene påvirker hvorvidt de to modellene for språkdeteksjon er enige. Vi ser at avsnitt som er kortere enn 10 tokens gir lav engihet, sannsynligvis fordi det er for lite informasjon til å kunne detektere språket med noe særlig sikkerhet. Avsnitt som er lengre enn 600 tokens introduserer også støy, så vi kutter disse. Med disse kuttene er fortsatt 98% av dataen beholdt (telt i antall tokens). 

### Språkstatistikk om samiske språk
Skriptet `language_statistics_per_text.py` lager språkstatistikk for bøker med avsnitt på minst ett av de samiske språkene innenfor avsnitt flere enn 10 tokens og færre enn 600 tokens. (Disse terskelverdiene er basert på det vi ser i notebooken `notebooks/plot_agreement.ipynb`)

Utfilene fra `language_statistics_per_text.py` viser at Gielladetect detekterer samisk i minst ett avsnitt i 379 150 bøker.  
For glotlid er det tilsvarende tallet 185 403.  (Disse filene er ganske store og ikke inkludert her).

Skriptet `create_files_for_delivery.py` leser utfilene fra `language_statistics_per_text.py`, filtrerer ut alle bøker hvor færre enn 10% av avsnittene er samisk (detektert), og henter metadata fra Nettbibliotekets items-api. Utfilene ligger i [data/sámi_language_statistics/](data/sámi_language_statistics). 
Det er en mappe per språkdeteksjonsmodell (gielladetect og glotlid). I hver mappe ligger det to filer, de har samme kolonner. Forskjellen er at i `paragraphs_stats.jsonl` er språkstatistikken beregnet på avsnittnivå (10% sørsamisk betyr at det ble detektert sørsamisk for 10% av avsnittene i boka). I `tokens_stats.jsonl` er språkstatistikken beregnet på tokennivå, vi har slått sammen tokens fra alle avsnitt, siden lengden varierer.

Filene har disse kolonnene: 
```
"title": bokas tittel 
"year": året boka ble utgitt
"names": forfattere/skapere
"detected_sme_share": andel detektert nordsamisk (flyttall fra 0 til 1) 
"detected_sma_share": andel detektert sørsamisk (flyttall fra 0 til 1)
"detected_smj_share": andel detektert lulesamisk (flyttall fra 0 til 1)
"detected_smi_share": andel detektert samiske språk (flyttall fra 0 til 1)
"detected_sms_share": andel detektert skoltesamisk (flyttall fra 0 til 1)
"detected_smn_share": andel detektert enaresamisk (flyttall fra 0 til 1)
"all_detected_languages": dict med {"språkkode": andel detektert dette språket} for alle detekterte språk i boka 
"library_languages": liste med språkkoder fra bibliotekets metadata 
"num_tokens": antall tokens i boka
"num_paragraphs": antall avsnitt i boka
"urn": id i nettbiblioteket (legg på https://www.nb.no/items/ foran så får du lenke til nettbiblioteket)
"dhlabid": id i boka
```

I notebooken `notebooks/sami_language_statistics.ipynb` ser vi på utfilene fra `create_file_for_delivery.py`.  
Vi ser på antall bøker på forskjellige samiske språk, og hvorvidt de detekterte språka stemmer overens med bibliotekets metadata.   
Vi ser spesifikt på hvilke bøker hvor lulesamisk er detektert av gielladetect, men ikke i metadata.  
M.a.o litt eksempelkode for hvordan man kan jobbe videre med disse dataene.  
