# Skript for å detektere språk på avsnittsnivå i DH-lab-databaser

Kjør skriptet i parallell, ved å bruke GNU parallel:

```bash
ls /data/db/ft/alto_1* | parallel -j4 "pdm run detect.py {} out"
```

## Laste ned HF-modell lokalt

```bash
mkdir models
pdm run hf download cis-lmu/glotlid model_v3.bin --local-dir ./models
```