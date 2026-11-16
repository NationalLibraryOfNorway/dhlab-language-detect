
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

### Analyse av språkdeteksjon-utfiler
Skriptene `count_...` analyserer utfilene fra språkdeteksjonen. 
De fordrer at filene fra språkdeteksjonen ligger på `data/db_langs/` (relativt til rota i denne mappa). 

### Lag språkstatistikk
Skriptet `create_statistics.py` lager språkstatistikk for bøker med avsnitt på minst ett av de samiske språkene innenfor avsnitt flere enn 10 tokens og færre enn 600 tokens.

### Lag JSONL-datasett
Skriptet 'create_jsonl.py' henter metadata fra Nettbiblioteket og lager spesifikke kolonner per samiske språk for bedre tolkbarhet. Skriptet kjøres ved å pipe resultatet fra `create_statistics.py`:

```bash
cat language_statistics_glotlid.jsonl | pdm run create_jsonl.py 
```
