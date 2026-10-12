# Skript for å detektere språk på avsnittsnivå i DH-lab-databaser

Kjør skriptet i parallell, ved å bruke GNU parallel:

```bash
ls /data/db/ft/alto_1* | parallel -j4 "pdm run detect.py {} out"
```