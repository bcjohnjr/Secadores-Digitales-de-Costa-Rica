#!/usr/bin/env python3
"""Secadores Digitales de Costa Rica — ERA5 historical weather downloader.

Downloads REAL ERA5 reanalysis data (not synthetic) for all 32 hydro-plant nodes
and 2 comparator sites.  Two backends are supported:

  Backend A — Open-Meteo Historical Weather API (DEFAULT, no account required)
    Uses ECMWF ERA5 data served by Open-Meteo.  No API key needed.
    Rate limit: ~10 000 requests/day on the free tier; this script batches and
    throttles automatically.

  Backend B — Copernicus CDS API (for authoritative ERA5 download)
    Requires a free CDS account: https://cds.climate.copernicus.eu/
    Set your credentials in ~/.cdsapirc (see --cds-setup for instructions).
    Gives the original ECMWF ERA5 GRIB files which are then converted to CSV.

Usage
-----
  python descargar_era5_costa_rica.py                       # full 2010–2025 (Open-Meteo)
  python descargar_era5_costa_rica.py --years 2024:2025     # two recent years
  python descargar_era5_costa_rica.py --years 2025          # quick single-year test
  python descargar_era5_costa_rica.py --backend cds         # use Copernicus CDS API
  python descargar_era5_costa_rica.py --cds-setup           # print CDS credential instructions
  python descargar_era5_costa_rica.py --dry-run             # list sites, no network calls
  python descargar_era5_costa_rica.py --daily               # also write daily aggregates

After downloading, run the model with:
  python ../03_Modelo/secadores_model.py --era5 Secadores_ERA5_historical

Data lineage
------------
- Backend A: ECMWF ERA5 served via Open-Meteo (https://open-meteo.com/)
  DOI: https://doi.org/10.24381/cds.adbb2d47
- Backend B: ECMWF ERA5 from Copernicus CDS
  DOI: https://doi.org/10.24381/cds.adbb2d47
  Citation: Hersbach et al. (2020) https://doi.org/10.1002/qj.3803

Limitations
-----------
- ERA5 is a reanalysis product, not direct measurements at each site.
- Spatial resolution ~0.25°; nearby nodes may share the same grid cell.
- Precipitation is atmospheric precipitation, NOT river discharge or hydro availability.
- Hydro generation availability requires ICE / CENCE actual operational records.
- Comparator campus coordinates are district/town proxies, not measured site coordinates.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterator, Optional

# ─── Configuration ────────────────────────────────────────────────────────────

OPEN_METEO_API = "https://archive-api.open-meteo.com/v1/archive"

# Hourly variables requested from Open-Meteo / ERA5
# Units returned: wind m/s, radiation W/m², temp °C, humidity %, pressure hPa, precip mm
VARIABLES = [
    "temperature_2m",           # °C — required for dryer energy balance
    "relative_humidity_2m",     # % — required for dryer inlet conditions
    "precipitation",            # mm/hr — required for sun-drying feasibility
    "shortwave_radiation",      # W/m² — solar resource
    "direct_normal_irradiance", # W/m² — for PV calculations
    "cloud_cover",              # % — sky conditions
    "wind_speed_100m",          # m/s at 100 m hub height — for any wind context
    "wind_direction_100m",      # ° — wind direction
    "surface_pressure",         # hPa — for psychrometric calculations
    "et0_fao_evapotranspiration",  # mm/day — agricultural water demand proxy
]

# These must be present and complete; missing any is a fatal error for that site-year
REQUIRED_VARIABLES = frozenset({
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "shortwave_radiation",
})

OPTIONAL_VARIABLES = [v for v in VARIABLES if v not in REQUIRED_VARIABLES]

# Variables to aggregate to daily for the model's sun-drying calculation
DAILY_AGG = {
    "temperature_2m":           ("mean", "min", "max"),
    "relative_humidity_2m":     ("mean",),
    "precipitation":            ("sum",),           # daily total mm
    "shortwave_radiation":      ("mean",),
    "cloud_cover":              ("mean",),
    "wind_speed_100m":          ("mean",),
    "et0_fao_evapotranspiration": ("sum",),
}

# Threshold for a "wet day" used in sun-drying window analysis (matches model)
WET_MM = 1.0   # mm/day total precipitation — same threshold as the model (secadores_model.py, sun_drying.wet_mm)

# Costa Rica local time is UTC−6 all year (no daylight saving)
UTC_OFFSET_H = -6

# ─── Sites ────────────────────────────────────────────────────────────────────

def _load_sites() -> list[tuple[str, float, float]]:
    here = Path(__file__).resolve().parent
    candidates = [
        here / "sites.json",
        here.parent / "03_Modelo" / "data" / "sites.json",
        here.parent / "code" / "data" / "sites.json",
    ]
    for path in candidates:
        if path.exists():
            rows = json.loads(path.read_text("utf-8"))
            return [(f"{r['id']:02d} {r['name']}", float(r["lat"]), float(r["lon"])) for r in rows]
    raise SystemExit(
        "sites.json not found. Expected next to this script or at "
        "03_Modelo/data/sites.json"
    )


COMPARATORS = [
    ("C1 Quantum AI Free Zone Campus (Limon proxy)", 9.99070, -83.03590),
    ("C2 Palo Negro AI HPC Campus (Bagaces proxy)",  10.66000, -85.20000),
]


# ─── Utilities ────────────────────────────────────────────────────────────────

def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def expected_hours(year: int) -> int:
    return 8784 if is_leap(year) else 8760


def atomic_write(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text to path atomically, handling OneDrive / cloud-sync file locks.

    OneDrive locks files while uploading them, causing atomic rename to fail with
    WinError 5 (Access is denied).  Strategy:
      1. Write to a hidden temp file (dot-prefix avoids OneDrive sync).
      2. Try rename; if it fails due to a lock, fall back to a direct overwrite.
      3. Retry the overwrite up to 5 times with short sleeps.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Dot-prefix keeps OneDrive from syncing the temp file
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(text, encoding=encoding)
    for attempt in range(5):
        try:
            tmp.replace(path)
            return
        except (PermissionError, OSError):
            # OneDrive lock — wait briefly then try a direct overwrite
            time.sleep(0.5 * (attempt + 1))
            try:
                path.write_text(text, encoding=encoding)
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
                return
            except (PermissionError, OSError):
                pass
    # Last resort: overwrite without temp (acceptable for the manifest)
    path.write_text(text, encoding=encoding)


def atomic_json(path: Path, obj: object) -> None:
    atomic_write(path, json.dumps(obj, indent=2, ensure_ascii=False))


def gzip_atomic_json(path: Path, obj: object) -> None:
    """Write gzip-JSON atomically with OneDrive lock resilience."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
        json.dump(obj, f, separators=(",", ":"))
    for attempt in range(5):
        try:
            tmp.replace(path)
            return
        except (PermissionError, OSError):
            time.sleep(0.5 * (attempt + 1))
    # Last resort: read-and-overwrite
    data = tmp.read_bytes()
    path.write_bytes(data)
    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass


def _onedrive_safe_replace(src: Path, dst: Path) -> None:
    """Rename src → dst, retrying on Windows OneDrive file-lock errors."""
    for attempt in range(6):
        try:
            src.replace(dst)
            return
        except (PermissionError, OSError):
            if attempt == 5:
                # Last resort: copy bytes directly
                dst.write_bytes(src.read_bytes())
                try:
                    src.unlink(missing_ok=True)
                except Exception:
                    pass
                return
            time.sleep(0.8 * (attempt + 1))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ─── Open-Meteo backend ───────────────────────────────────────────────────────

def _om_url(lat: float, lon: float, year: int) -> str:
    params = {
        "latitude":         f"{lat:.5f}",
        "longitude":        f"{lon:.5f}",
        "start_date":       f"{year}-01-01",
        "end_date":         f"{year}-12-31",
        "hourly":           ",".join(VARIABLES),
        "models":           "era5",          # always request the pure ERA5 model
        "timezone":         "GMT",           # all timestamps in UTC
        "wind_speed_unit":  "ms",
    }
    return OPEN_METEO_API + "?" + urllib.parse.urlencode(params)


def _http_get_json(url: str, attempts: int = 8, name: str = "") -> dict:
    """Fetch a JSON URL with exponential back-off; raises RuntimeError on failure."""
    last_msg = ""
    for n in range(attempts):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "SecadoresDigitalesHistoricalWeather/2.0 (research)",
                "Accept":     "application/json",
            })
            with urllib.request.urlopen(req, timeout=240) as resp:
                raw = json.load(resp)
            if not isinstance(raw, dict):
                raise ValueError("API returned a non-object JSON response")
            if raw.get("error"):
                raise ValueError("API error: " + str(raw.get("reason", raw)))
            return raw
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504):
                body = ""
                try:
                    body = exc.read(800).decode("utf-8", errors="replace")
                except Exception:
                    pass
                raise RuntimeError(f"HTTP {exc.code} for {name}: {body}") from exc
            last_msg = f"HTTP {exc.code} (server busy / rate limit)"
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_msg = str(exc)
        pause = min(5 * 2 ** n, 120)
        print(f"  [{name}] Transient error ({last_msg}); retry in {pause}s…", flush=True)
        time.sleep(pause)
    raise RuntimeError(
        f"Download failed after {attempts} attempts for {name}.\n"
        f"Last error: {last_msg}\nURL: {url}"
    )


def _validate_hourly(hourly: dict, year: int, name: str) -> int:
    """Validate shape and required columns; return hour count."""
    n = expected_hours(year)
    times = hourly.get("time")
    if not isinstance(times, list) or len(times) != n:
        got = len(times) if isinstance(times, list) else "missing"
        raise ValueError(f"{name} {year}: expected {n} hours, got {got}")
    if times[0] != f"{year}-01-01T00:00" or times[-1] != f"{year}-12-31T23:00":
        raise ValueError(
            f"{name} {year}: unexpected timestamp bounds "
            f"{times[0]} … {times[-1]}"
        )
    for v in REQUIRED_VARIABLES:
        col = hourly.get(v)
        if not isinstance(col, list) or len(col) != n:
            raise ValueError(f"{name} {year}: required variable '{v}' missing or wrong length")
        if any(x is None for x in col):
            raise ValueError(f"{name} {year}: required variable '{v}' contains null values")
    return n


def fetch_om_year(lat: float, lon: float, year: int, name: str) -> dict:
    """Fetch one site-year from Open-Meteo and return the validated API response."""
    url = _om_url(lat, lon, year)
    raw = _http_get_json(url, name=name)
    hourly = raw.get("hourly", {})
    _validate_hourly(hourly, year, name)
    # Annotate with provenance metadata before caching
    raw["_secadores_provenance"] = {
        "backend":          "open-meteo-era5",
        "model_requested":  "era5",
        "url":              url,
        "retrieved_utc":    dt.datetime.now(dt.timezone.utc).isoformat(),
        "site":             name,
        "year":             year,
        "is_real_era5":     True,
        "doi":              "https://doi.org/10.24381/cds.adbb2d47",
    }
    return raw


# ─── CDS backend (Copernicus Climate Data Store) ──────────────────────────────

CDS_VARIABLES_MAP = {
    # ERA5 CDS short name → model variable name
    "2m_temperature":               "temperature_2m",
    "2m_relative_humidity":         "relative_humidity_2m",
    "total_precipitation":          "precipitation",
    "surface_solar_radiation_downwards": "shortwave_radiation",
    "total_cloud_cover":            "cloud_cover",
    "10m_u_component_of_wind":      "_u10",
    "10m_v_component_of_wind":      "_v10",
    "surface_pressure":             "surface_pressure",
}

def _print_cds_setup() -> None:
    print(textwrap.dedent("""
        ════════════════════════════════════════════════════════════
        HOW TO SET UP THE COPERNICUS CDS API (Backend B)
        ════════════════════════════════════════════════════════════

        1. Create a free account at: https://cds.climate.copernicus.eu/
        2. After login, go to your profile → API key
        3. Copy your UID and API key, then create the file:
               ~/.cdsapirc          (Linux/macOS)
               C:\\Users\\YourName\\.cdsapirc   (Windows)
           with exactly this content (substitute your values):

               url: https://cds.climate.copernicus.eu/api/v2
               key: YOUR-UID:YOUR-API-KEY
               verify: 1

        4. Install the CDS client:
               pip install cdsapi

        5. Run with --backend cds:
               python descargar_era5_costa_rica.py --backend cds

        The CDS API is free but has a queue; large requests can take
        hours.  The Open-Meteo backend (default) is much faster for
        this use case and uses the same ERA5 source data.
        ════════════════════════════════════════════════════════════
    """))


def fetch_cds_year(lat: float, lon: float, year: int, name: str, out_dir: Path) -> dict:
    """Download one site-year via the Copernicus CDS API.

    Requires cdsapi installed and ~/.cdsapirc configured.
    Returns the same structure as fetch_om_year so the rest of the pipeline
    is backend-agnostic.
    """
    try:
        import cdsapi  # type: ignore
    except ImportError:
        raise RuntimeError(
            "cdsapi not installed. Run: pip install cdsapi\n"
            "Then configure ~/.cdsapirc  (run --cds-setup for instructions)."
        )

    grib_path = out_dir / f"{slug(name)}_{year}_cds.grib"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Bounding box: 0.5° padding around the site
    area = [round(lat + 0.5, 1), round(lon - 0.5, 1),
            round(lat - 0.5, 1), round(lon + 0.5, 1)]   # N, W, S, E

    c = cdsapi.Client()
    if not grib_path.exists():
        print(f"  Submitting CDS request for {name} {year} (may queue for hours)…", flush=True)
        c.retrieve(
            "reanalysis-era5-single-levels",
            {
                "product_type": "reanalysis",
                "variable": list(CDS_VARIABLES_MAP.keys()),
                "year":  str(year),
                "month": [f"{m:02d}" for m in range(1, 13)],
                "day":   [f"{d:02d}" for d in range(1, 32)],
                "time":  [f"{h:02d}:00" for h in range(24)],
                "area":  area,
                "format": "grib",
            },
            str(grib_path),
        )
        print(f"  CDS download complete: {grib_path.name}", flush=True)

    # Convert GRIB to the same hourly dict structure used by the Open-Meteo backend
    try:
        import eccodes  # type: ignore  (pip install eccodes)
    except ImportError:
        raise RuntimeError(
            "eccodes not installed. Run: pip install eccodes\n"
            "Required to read the CDS GRIB files."
        )

    return _grib_to_hourly_dict(grib_path, lat, lon, year, name)


def _grib_to_hourly_dict(grib_path: Path, lat: float, lon: float, year: int, name: str) -> dict:
    """Convert ERA5 GRIB (single-levels, hourly) to Open-Meteo-compatible dict."""
    import eccodes  # type: ignore

    n_hours = expected_hours(year)
    start = dt.datetime(year, 1, 1, 0, tzinfo=dt.timezone.utc)
    times = [(start + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(n_hours)]

    # Collect by variable and timestamp
    data: dict[str, dict[str, float]] = {v: {} for v in CDS_VARIABLES_MAP.values()
                                          if not v.startswith("_")}
    data["wind_speed_100m"] = {}   # synthesised from u/v
    u10: dict[str, float] = {}
    v10: dict[str, float] = {}

    with grib_path.open("rb") as f:
        while True:
            gid = eccodes.codes_grib_new_from_file(f)
            if gid is None:
                break
            try:
                short = eccodes.codes_get(gid, "shortName")
                step_range = eccodes.codes_get(gid, "stepRange")
                valid_dt = eccodes.codes_get(gid, "validityDate")
                valid_t = eccodes.codes_get(gid, "validityTime")
                ts = f"{valid_dt:08d}"[:4] + "-" + f"{valid_dt:08d}"[4:6] + \
                     "-" + f"{valid_dt:08d}"[6:8] + "T" + f"{valid_t:04d}"[:2] + ":00"
                # Nearest grid point to requested coordinate
                lats = eccodes.codes_get_array(gid, "latitudes")
                lons = eccodes.codes_get_array(gid, "longitudes")
                vals = eccodes.codes_get_array(gid, "values")
                idx = int(((lats - lat) ** 2 + (lons - lon) ** 2).argmin())
                val = float(vals[idx])
                cds_name = {
                    "2t":  "temperature_2m",
                    "r":   "relative_humidity_2m",
                    "tp":  "precipitation",
                    "ssrd":"shortwave_radiation",
                    "tcc": "cloud_cover",
                    "u10": "_u10",
                    "v10": "_v10",
                    "sp":  "surface_pressure",
                }.get(short)
                if cds_name == "temperature_2m":
                    val -= 273.15          # K → °C
                elif cds_name == "shortwave_radiation":
                    val /= 3600.0          # J/m² (accumulated) → W/m² average
                elif cds_name == "precipitation":
                    val = max(0.0, val * 1000.0)  # m → mm
                elif cds_name == "surface_pressure":
                    val /= 100.0           # Pa → hPa
                elif cds_name == "tcc":
                    val *= 100.0           # fraction → %
                if cds_name == "_u10":
                    u10[ts] = val
                elif cds_name == "_v10":
                    v10[ts] = val
                elif cds_name and not cds_name.startswith("_"):
                    data[cds_name][ts] = val
            finally:
                eccodes.codes_release(gid)

    # Synthesise wind speed from u/v (100 m not in single-levels; use 10 m as proxy)
    for ts in times:
        u = u10.get(ts, 0.0)
        v = v10.get(ts, 0.0)
        data["wind_speed_100m"][ts] = (u ** 2 + v ** 2) ** 0.5

    hourly: dict = {"time": times}
    for var in VARIABLES:
        if var in data:
            hourly[var] = [data[var].get(ts) for ts in times]
        else:
            hourly[var] = [None] * n_hours

    result = {
        "latitude": lat, "longitude": lon, "utc_offset_seconds": 0,
        "hourly": hourly,
        "hourly_units": {
            "temperature_2m": "°C", "relative_humidity_2m": "%",
            "precipitation": "mm", "shortwave_radiation": "W/m²",
            "cloud_cover": "%", "wind_speed_100m": "m/s",
            "surface_pressure": "hPa",
        },
        "_secadores_provenance": {
            "backend":         "copernicus-cds-era5",
            "model_requested": "era5",
            "grib_file":       str(grib_path),
            "retrieved_utc":   dt.datetime.now(dt.timezone.utc).isoformat(),
            "site":            name,
            "year":            year,
            "is_real_era5":    True,
            "doi":             "https://doi.org/10.24381/cds.adbb2d47",
        },
    }
    _validate_hourly(result["hourly"], year, name)
    return result


# ─── Daily aggregation ────────────────────────────────────────────────────────

def _hourly_to_daily(hourly: dict, year: int, name: str) -> list[dict]:
    """Convert UTC hourly to Costa Rica local daily aggregates (UTC−6)."""
    times = hourly["time"]
    n = len(times)

    # Build a mapping: local date string → list of hourly indices
    date_indices: dict[str, list[int]] = {}
    for i, ts in enumerate(times):
        # Parse UTC timestamp "YYYY-MM-DDTHH:MM"
        utc_dt = dt.datetime(int(ts[:4]), int(ts[5:7]), int(ts[8:10]),
                             int(ts[11:13]), tzinfo=dt.timezone.utc)
        local_dt = utc_dt + dt.timedelta(hours=UTC_OFFSET_H)
        local_date = local_dt.strftime("%Y-%m-%d")
        date_indices.setdefault(local_date, []).append(i)

    # Only keep dates fully within the requested year in local time
    daily_rows = []
    for date_str in sorted(date_indices):
        local_year = int(date_str[:4])
        if local_year != year:
            continue
        idx = date_indices[date_str]
        row: dict = {"date_local": date_str, "site": name, "n_hours": len(idx)}
        for var, aggs in DAILY_AGG.items():
            col = hourly.get(var)
            if not isinstance(col, list):
                vals = []
            else:
                vals = [col[i] for i in idx if col[i] is not None]
            for agg in aggs:
                key = f"{var}_{agg}"
                if not vals:
                    row[key] = None
                elif agg == "mean":
                    row[key] = sum(vals) / len(vals)
                elif agg == "sum":
                    row[key] = sum(vals)
                elif agg == "min":
                    row[key] = min(vals)
                elif agg == "max":
                    row[key] = max(vals)
        precip_sum = row.get("precipitation_sum")
        row["wet_day"] = 1 if (precip_sum is not None and precip_sum >= WET_MM) else 0
        daily_rows.append(row)
    return daily_rows


# ─── Cache helpers ────────────────────────────────────────────────────────────

def load_cached(path: Path, year: int, name: str) -> dict | None:
    if not path.exists():
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            cached = json.load(f)
        _validate_hourly(cached.get("hourly", {}), year, name)
        return cached
    except Exception as exc:
        print(f"  Ignoring corrupt cache {path.name}: {exc}", flush=True)
        path.rename(path.with_name(path.name + ".invalid"))
        return None


# ─── Output writers ───────────────────────────────────────────────────────────

def write_hourly_csv(path: Path, rows: list[dict], name: str,
                      lat: float, lon: float, era5_lat: float | None,
                      era5_lon: float | None) -> None:
    """Write (or append) hourly rows to a gzip-CSV file."""
    header = ["time_utc", "community", "requested_lat", "requested_lon",
              "era5_grid_lat", "era5_grid_lon"] + VARIABLES
    tmp = path.with_name(path.name + ".part")
    with gzip.open(tmp, "wt", encoding="utf-8", newline="", compresslevel=6) as f:
        w = csv.writer(f)
        w.writerow(header)
        times = rows["time"]
        n = len(times)
        cols = [rows.get(v) for v in VARIABLES]
        for i, ts in enumerate(times):
            w.writerow([
                ts, name, lat, lon, era5_lat, era5_lon,
            ] + [
                (col[i] if isinstance(col, list) and len(col) == n else None)
                for col in cols
            ])
    tmp.replace(path)


def write_daily_csv(path: Path, daily_rows: list[dict]) -> None:
    if not daily_rows:
        return
    fields = list(daily_rows[0].keys())
    tmp = path.with_name("." + path.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", newline="", compresslevel=6) as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(daily_rows)
    _onedrive_safe_replace(tmp, path)


# ─── ZIP archive ──────────────────────────────────────────────────────────────

def make_zip(folder: Path, first: int, last: int) -> Path:
    archive = folder.parent / f"Secadores_Digitales_ERA5_{first}_{last}_DATA.zip"
    tmp = archive.with_suffix(".zip.part")
    if tmp.exists():
        tmp.unlink()
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=5, allowZip64=True) as z:
        for f in sorted(folder.rglob("*")):
            if f.is_file() and not f.name.endswith((".part", ".invalid")):
                z.write(f, f.relative_to(folder.parent))
    tmp.replace(archive)
    with zipfile.ZipFile(archive) as z:
        err = z.testzip()
        if err:
            raise RuntimeError(f"ZIP integrity check failed on: {err}")
    return archive


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--years", default="2010:2025",
        help="Year or inclusive range, e.g. 2025 or 2010:2025 (default: 2010:2025)",
    )
    parser.add_argument(
        "--output", default="Secadores_ERA5_historical",
        help="Output folder (default: Secadores_ERA5_historical)",
    )
    parser.add_argument(
        "--backend", choices=["open-meteo", "cds"], default="open-meteo",
        help="Data backend: open-meteo (default, no account) or cds (Copernicus, needs ~/.cdsapirc)",
    )
    parser.add_argument(
        "--cds-setup", action="store_true",
        help="Print instructions for setting up the Copernicus CDS API and exit",
    )
    parser.add_argument(
        "--site", action="append", metavar="NAME",
        help="Download only this site name (repeat for multiple). Use --dry-run to see all names.",
    )
    parser.add_argument(
        "--daily", action="store_true",
        help="Also write daily aggregated CSV per site (local Costa Rica time, UTC−6)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List all sites and exit without making any network requests",
    )
    parser.add_argument(
        "--delay", type=float, default=0.15,
        help="Seconds between requests (default 0.15; increase if rate-limited)",
    )
    args = parser.parse_args()

    if args.cds_setup:
        _print_cds_setup()
        return 0

    # Parse year range
    try:
        parts = args.years.split(":")
        if len(parts) not in (1, 2):
            raise ValueError
        first, last = int(parts[0]), int(parts[-1])
        if not (1940 <= first <= last <= dt.datetime.now(dt.timezone.utc).year):
            raise ValueError
    except ValueError:
        parser.error("--years must be YYYY or YYYY:YYYY, e.g. 2010:2025")

    # Build site list
    node_sites = _load_sites()
    all_sites = node_sites + COMPARATORS
    if args.site:
        wanted = set(args.site)
        unknown = wanted - {s[0] for s in all_sites}
        if unknown:
            parser.error(f"Unknown site(s): {unknown!r}\nUse --dry-run to see valid names.")
        selected = [s for s in all_sites if s[0] in wanted]
    else:
        selected = all_sites

    # Dry run
    if args.dry_run:
        print(f"{'ID':>4}  {'Site':45s}  {'Lat':>10}  {'Lon':>11}")
        print("-" * 75)
        for i, (name, lat, lon) in enumerate(selected, 1):
            print(f"{i:>4}  {name:45s}  {lat:>10.5f}  {lon:>11.5f}")
        print(f"\n{len(selected)} sites  ·  years {first}–{last}  ·  "
              f"backend: {args.backend}  ·  no download")
        return 0

    out = Path(args.output).resolve()
    raw_dir = out / "raw_cache"
    out.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(exist_ok=True)

    # Provenance manifest
    manifest = {
        "description":           "ERA5 hourly reanalysis — REAL observational reanalysis data (not synthetic)",
        "backend":               args.backend,
        "provider":              "Open-Meteo (https://open-meteo.com/)" if args.backend == "open-meteo"
                                 else "Copernicus Climate Data Store (https://cds.climate.copernicus.eu/)",
        "underlying_data":       "ECMWF ERA5 Reanalysis",
        "doi":                   "https://doi.org/10.24381/cds.adbb2d47",
        "citation":              (
            "Hersbach, H. et al. (2020). The ERA5 global reanalysis. "
            "Quarterly Journal of the Royal Meteorological Society, 146(730), 1999–2049. "
            "https://doi.org/10.1002/qj.3803"
        ),
        "api_docs":              (
            "https://open-meteo.com/en/docs/historical-weather-api"
            if args.backend == "open-meteo" else
            "https://cds.climate.copernicus.eu/api-how-to"
        ),
        "variables":             VARIABLES,
        "required_variables":    sorted(REQUIRED_VARIABLES),
        "optional_variables":    OPTIONAL_VARIABLES,
        "wet_day_threshold_mm":  WET_MM,
        "local_timezone":        "UTC−6 (Costa Rica, no DST)",
        "first_year":            first,
        "last_year":             last,
        "n_sites":               len(selected),
        "sites":                 [{"name": n, "lat": la, "lon": lo} for n, la, lo in selected],
        "started_utc":           dt.datetime.now(dt.timezone.utc).isoformat(),
        "downloads":             [],
        "status":                "running",
        "limitations": [
            "ERA5 is reanalysis (assimilation of observations), not measured mast data.",
            "Spatial resolution ~0.25°; nearby nodes may share a grid cell.",
            "Precipitation is atmospheric; it is NOT river discharge or hydro availability.",
            "Hydro generation requires ICE/CENCE actual operational records.",
            "Comparator coordinates are district proxies, not measured parcel coordinates.",
            "wind_speed_100m from Open-Meteo is interpolated from ERA5 model levels.",
            "CDS backend: wind at 100 m not in ERA5 single levels; 10-m speed is substituted.",
        ],
    }
    manifest_path = out / "provenance_manifest.json"
    atomic_json(manifest_path, manifest)

    total = len(selected) * (last - first + 1)
    done = 0
    print(
        f"\nERA5 historical weather download\n"
        f"  Backend : {args.backend}\n"
        f"  Years   : {first}–{last}\n"
        f"  Sites   : {len(selected)}\n"
        f"  Output  : {out}\n",
        flush=True,
    )

    try:
        for name, lat, lon in selected:
            site_slug = slug(name)
            site_raw_dir = raw_dir / site_slug
            site_raw_dir.mkdir(exist_ok=True)
            hourly_csv = out / f"{site_slug}_hourly_era5.csv.gz"
            daily_csv  = out / f"{site_slug}_daily_era5.csv.gz"
            all_daily: list[dict] = []

            tmp_hourly = hourly_csv.with_name("." + hourly_csv.name + ".tmp")
            h_header = ["time_utc", "community", "requested_lat", "requested_lon",
                        "era5_grid_lat", "era5_grid_lon"] + VARIABLES

            with gzip.open(tmp_hourly, "wt", encoding="utf-8", newline="",
                           compresslevel=6) as hf:
                hw = csv.writer(hf)
                hw.writerow(h_header)

                for year in range(first, last + 1):
                    cache_path = site_raw_dir / f"{year}.json.gz"
                    cached = load_cached(cache_path, year, name)
                    from_cache = cached is not None
                    if not from_cache:
                        print(f"[{done+1}/{total}] Downloading {name} {year}…", flush=True)
                        if args.backend == "open-meteo":
                            cached = fetch_om_year(lat, lon, year, name)
                        else:
                            cached = fetch_cds_year(lat, lon, year, name, site_raw_dir)
                        gzip_atomic_json(cache_path, cached)
                        if args.delay > 0:
                            time.sleep(args.delay)
                    else:
                        print(f"[{done+1}/{total}] Using cache: {name} {year}", flush=True)

                    hourly = cached["hourly"]
                    n = _validate_hourly(hourly, year, name)
                    era5_lat = cached.get("latitude")
                    era5_lon = cached.get("longitude")
                    cols = [hourly.get(v) for v in VARIABLES]

                    for i, ts in enumerate(hourly["time"]):
                        hw.writerow(
                            [ts, name, lat, lon, era5_lat, era5_lon]
                            + [(col[i] if isinstance(col, list) and len(col) == n else None)
                               for col in cols]
                        )

                    if args.daily:
                        all_daily.extend(_hourly_to_daily(hourly, year, name))

                    # Update manifest
                    sha = sha256_file(cache_path)
                    missing = {
                        v: (
                            sum(1 for x in hourly.get(v, []) if x is None)
                            if isinstance(hourly.get(v), list) else n
                        )
                        for v in VARIABLES
                    }
                    manifest["downloads"].append({
                        "site": name, "year": year,
                        "source": "cache" if from_cache else args.backend,
                        "cache_file": str(cache_path.relative_to(out)).replace(os.sep, "/"),
                        "sha256": sha,
                        "n_hours": n,
                        "era5_grid_lat": era5_lat,
                        "era5_grid_lon": era5_lon,
                        "missing_hours": {k: v for k, v in missing.items() if v > 0},
                    })
                    done += 1
                    manifest["completed"] = done
                    # Manifest written once per site (below), not every year,
                    # to avoid triggering OneDrive file-lock errors on Windows.

            # Write manifest once per site — far less OneDrive contention
            atomic_json(manifest_path, manifest)

            # Finalise hourly CSV (OneDrive-safe rename)
            _onedrive_safe_replace(tmp_hourly, hourly_csv)
            print(f"  → {hourly_csv.name}", flush=True)

            # Write daily CSV
            if args.daily and all_daily:
                write_daily_csv(daily_csv, all_daily)
                print(f"  → {daily_csv.name} ({len(all_daily)} daily rows)", flush=True)

    except (ValueError, RuntimeError, OSError, KeyboardInterrupt) as exc:
        manifest["status"] = "interrupted; re-run the same command to resume"
        manifest["error"] = str(exc)
        atomic_json(manifest_path, manifest)
        print(
            f"\n{'KeyboardInterrupt' if isinstance(exc, KeyboardInterrupt) else 'ERROR'}: {exc}",
            file=sys.stderr,
        )
        print("Run the SAME command to resume — completed years are cached.", file=sys.stderr)
        return 1

    # Finalise manifest
    manifest["status"] = "complete"
    manifest["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    atomic_json(manifest_path, manifest)

    # Create zip archive
    archive = make_zip(out, first, last)
    total_hours = sum(d["n_hours"] for d in manifest["downloads"])
    print(
        f"\n{'═'*60}\n"
        f"COMPLETE — {done} site-years, {total_hours:,} hourly records\n"
        f"Folder  : {out}\n"
        f"Archive : {archive}\n"
        f"{'═'*60}\n"
        f"\nNext step — run the model with real ERA5 data:\n"
        f"  cd ../03_Modelo\n"
        f"  python secadores_model.py --era5 {out}\n",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
