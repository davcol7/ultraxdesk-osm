#!/usr/bin/env python3
"""Prepara i "quadretti" di strade e sentieri di OpenStreetMap per il fondo del percorso di UltraXDesk.

Legge un file .osm.pbf (già ridotto alle vie con `highway`, ma va bene anche intero), tiene per ogni via solo le
etichette che servono al fondo (highway, surface, tracktype, sac_scale, smoothness) e la sua forma, e la scrive in
uno o più quadretti di CELLA x CELLA gradi: un file gzip JSON per quadretto, più l'indice `indice.json`.

Formato di un quadretto (q_<riga>_<colonna>.json.gz, riga = floor(lat / CELLA), colonna = floor(lon / CELLA)):

    {"v": 1, "riga": 90, "colonna": 27,
     "etichette": [["path", null, null, "mountain_hiking", null], ...],
     "vie": [[id, etichetta, lat0, lon0, dlat1, dlon1, dlat2, dlon2, ...], ...]}

con le coordinate in centomillesimi di grado (1e-5, circa 1 m): la prima assoluta, le altre come differenza dalla
precedente. Una via che attraversa più quadretti compare in ognuno.

Uso: python3 quadretti.py vie.osm.pbf cartella-uscita --data 2026-11-02 --regioni "Italia, Slovenia"
"""
import argparse
import gzip
import json
import math
import os
import shutil
import sys
import tempfile

import osmium

CELLA = 0.5           # gradi
SCALA = 100_000       # coordinate in 1e-5 gradi
ETICHETTE = ("highway", "surface", "tracktype", "sac_scale", "smoothness")
# le stesse vie escluse dalla ricerca su Overpass dell'app
ESCLUSE = {"proposed", "construction", "platform", "bus_stop", "elevator", "corridor", "raceway",
           "abandoned", "razed", "disused", "no", "planned"}


def cella(lat, lon):
    return math.floor(lat / CELLA), math.floor(lon / CELLA)


class Lettore(osmium.SimpleHandler):
    """Scrive ogni via in un file temporaneo per quadretto (una riga per via): così la memoria resta poca."""

    def __init__(self, temp):
        super().__init__()
        self.temp = temp
        self.file = {}
        self.vie = 0
        self.scartate = 0

    def scrivi(self, chiave, riga):
        f = self.file.get(chiave)
        if f is None:
            f = self.file[chiave] = open(os.path.join(self.temp, f"{chiave[0]}_{chiave[1]}.txt"), "a", encoding="utf-8")
        f.write(riga)

    def way(self, w):
        hw = w.tags.get("highway")
        if hw is None or hw in ESCLUSE:
            return
        punti = []
        for n in w.nodes:
            if not n.location.valid():
                continue
            punti.append((round(n.location.lat * SCALA), round(n.location.lon * SCALA)))
        if len(punti) < 2:
            self.scartate += 1
            return
        etichette = [w.tags.get(k) for k in ETICHETTE]
        # quadretti toccati: quelli del riquadro della via (le vie sono corte rispetto a un quadretto)
        lat = [p[0] for p in punti]
        lon = [p[1] for p in punti]
        r0, c0 = cella(min(lat) / SCALA, min(lon) / SCALA)
        r1, c1 = cella(max(lat) / SCALA, max(lon) / SCALA)
        coord = [punti[0][0], punti[0][1]]
        for i in range(1, len(punti)):
            coord += [punti[i][0] - punti[i - 1][0], punti[i][1] - punti[i - 1][1]]
        riga = json.dumps([w.id, etichette, coord], separators=(",", ":")) + "\n"
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                self.scrivi((r, c), riga)
        self.vie += 1
        if self.vie % 500_000 == 0:
            print(f"  {self.vie:,} vie lette", flush=True)

    def chiudi(self):
        for f in self.file.values():
            f.close()


def quadretto(percorso, riga, colonna):
    """Dal file temporaneo al quadretto: senza doppioni (estratti di regioni vicine), con l'elenco delle etichette."""
    viste = set()
    etichette = {}
    vie = []
    with open(percorso, encoding="utf-8") as f:
        for linea in f:
            id_, et, coord = json.loads(linea)
            if id_ in viste:
                continue
            viste.add(id_)
            chiave = tuple(et)
            if chiave not in etichette:
                etichette[chiave] = len(etichette)
            vie.append([id_, etichette[chiave]] + coord)
    return {"v": 1, "riga": riga, "colonna": colonna,
            "etichette": [list(k) for k in etichette], "vie": vie}


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("pbf", help="file .osm.pbf da leggere")
    a.add_argument("uscita", help="cartella dei quadretti (viene svuotata)")
    a.add_argument("--data", required=True, help="data dei dati (AAAA-MM-GG)")
    a.add_argument("--regioni", default="", help="nomi delle regioni, per l'indice")
    args = a.parse_args()

    if os.path.isdir(args.uscita):
        shutil.rmtree(args.uscita)
    os.makedirs(args.uscita)
    temp = tempfile.mkdtemp(prefix="quadretti-")
    try:
        print(f"Leggo {args.pbf}…", flush=True)
        lettore = Lettore(temp)
        lettore.apply_file(args.pbf, locations=True, idx="flex_mem")
        lettore.chiudi()
        print(f"{lettore.vie:,} vie in {len(lettore.file)} quadretti ({lettore.scartate} senza coordinate)", flush=True)

        indice = {}
        totale = 0
        for (r, c) in sorted(lettore.file):
            q = quadretto(os.path.join(temp, f"{r}_{c}.txt"), r, c)
            nome = f"q_{r}_{c}.json.gz"
            percorso = os.path.join(args.uscita, nome)
            with gzip.open(percorso, "wt", encoding="utf-8", compresslevel=9) as f:
                json.dump(q, f, separators=(",", ":"))
            peso = os.path.getsize(percorso)
            totale += peso
            indice[f"{r}_{c}"] = {"file": nome, "vie": len(q["vie"]), "byte": peso}
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    with open(os.path.join(args.uscita, "indice.json"), "w", encoding="utf-8") as f:
        json.dump({"v": 1, "data": args.data, "regioni": args.regioni, "cella": CELLA, "scala": SCALA,
                   "etichette": list(ETICHETTE), "quadretti": indice}, f, ensure_ascii=False, indent=1)
    grande = max(indice.values(), key=lambda x: x["byte"], default=None)
    print(f"Fatto: {len(indice)} quadretti, {totale / 1e6:.1f} MB in tutto"
          + (f", il più grande {grande['file']} di {grande['byte'] / 1e6:.1f} MB" if grande else ""), flush=True)
    if not indice:
        sys.exit("Nessuna via trovata: il file è vuoto o sbagliato.")


if __name__ == "__main__":
    main()
