"""Extract Costa Rica-region coastline and national borders from basemap-data GSHHS/WDB files
(intermediate resolution) into data/cr_outline.json. Run once; requires the basemap_data folder."""
import json, sys
from pathlib import Path
import numpy as np
src = Path(sys.argv[1]); out = Path(sys.argv[2])
BBOX = (-86.6, -82.2, 7.9, 11.4)
def read(kind, res="i"):
    meta = (src / f"{kind}meta_{res}.dat").read_text().splitlines()
    raw = (src / f"{kind}_{res}.dat").read_bytes()
    lines = []
    for m in meta:
        p = m.split()
        npts, s, n, off, nb = int(p[2]), float(p[3]), float(p[4]), int(p[5]), int(p[6])
        if n < BBOX[2] or s > BBOX[3]:
            continue
        a = np.frombuffer(raw[off:off + nb], dtype="<f4").reshape(-1, 2)
        lon, lat = a[:, 0].astype(float), a[:, 1].astype(float)
        sel = (lon > BBOX[0]) & (lon < BBOX[1]) & (lat > BBOX[2]) & (lat < BBOX[3])
        if sel.sum() < 2:
            continue
        lines.append([[round(x, 4), round(y, 4)] for x, y in zip(lon, lat)])
    return lines
data = {"coast": read("gshhs"), "borders": read("countries"),
        "source": "GSHHS/WDB intermediate resolution via basemap-data 2.0.0 (LGPL); clipped to Costa Rica region"}
out.write_text(json.dumps(data))
print(len(data["coast"]), len(data["borders"]), sum(len(l) for l in data["coast"]))
