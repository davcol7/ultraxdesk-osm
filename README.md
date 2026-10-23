# ultraxdesk-osm

Strade e sentieri di **OpenStreetMap** per il calcolo del fondo del percorso di
[UltraXDesk](https://github.com/davcol7/ultraxdesk) (repository privato). Qui non c'è niente dell'app né dei suoi
utenti: solo i dati pubblici di OpenStreetMap, ridotti a quello che serve al fondo, e lo script che li prepara.

## Cosa c'è

- `regioni.txt`: le regioni di [Geofabrik](https://download.geofabrik.de) da cui partire (oggi Italia, Slovenia,
  Croazia, Austria e Svizzera). Per aggiungerne o toglierne una basta cambiare una riga.
- `quadretti.py`: tiene di ogni via solo `highway`, `surface`, `tracktype`, `sac_scale`, `smoothness` e la forma, e
  divide tutto in **quadretti** di 0,5 × 0,5 gradi (circa 55 × 40 km): un file `q_<riga>_<colonna>.json.gz` per
  quadretto, più `indice.json` con data, regioni e l'elenco dei quadretti.
- `.github/workflows/quadretti.yml`: l'azione che il **2 di ogni mese** (o quando premi *Run workflow* in *Actions*)
  scarica le regioni, prepara i quadretti e li pubblica come **release** "latest". Restano le ultime 3 release.

UltraXDesk, quando calcoli il fondo di una gara, scarica da
`https://github.com/davcol7/ultraxdesk-osm/releases/latest/download/` solo l'indice e i quadretti che la traccia
attraversa, calcola il fondo e li butta: il fondo resta salvato nella gara.

## Formato di un quadretto

```json
{"v": 1, "riga": 90, "colonna": 27,
 "etichette": [["path", null, null, "mountain_hiking", null], ...],
 "vie": [[id, etichetta, lat0, lon0, dlat1, dlon1, ...], ...]}
```

`riga = floor(lat / 0,5)`, `colonna = floor(lon / 0,5)`. Le etichette sono nell'ordine di `indice.json`
(`highway`, `surface`, `tracktype`, `sac_scale`, `smoothness`); le coordinate sono in centomillesimi di grado
(circa 1 m), la prima assoluta e le altre come differenza dalla precedente. Una via che attraversa più quadretti
compare in ognuno.

## Provarlo sul tuo computer

```bash
pip install osmium            # e osmium-tool, se vuoi ridurre prima il file
python3 quadretti.py croatia-latest.osm.pbf quadretti --data 2026-11-02 --regioni "Croazia"
```

## Licenza

I dati sono © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), con licenza
[ODbL](https://opendatacommons.org/licenses/odbl/); gli estratti vengono da Geofabrik.
