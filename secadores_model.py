#!/usr/bin/env python3
"""Secadores Digitales de Costa Rica — network model (prefeasibility screen).

Monthly model of a 32-node hydro-adjacent AI computing network whose recovered
liquid-cooling heat (45-55 C) warms recirculating camaron (Litopenaeus vannamei)
aquaculture and dries every wet product within reach of a node, in priority order:
fruit for retail (mango, pineapple, banana, plantain), camaron/snapper by-product meal,
coffee parchment (service drying for beneficios), banana meal for cattle and poultry,
pineapple stubble, coffee pulp and rainy-season hay. Dryer technology options are open
(once-through warm air) and closed-loop heat-pump dehumidifying dryers assisted by
data-centre heat, whose condensate is allocated to treated retail distilled water
(capped), RAS make-up water and irrigation. Also: the camaron <-> spotted rose snapper
(Lutjanus guttatus) meal loop; farmer drying economics versus sun drying; ICE
supply-permission scenarios; and a comparison with two proposed AI campuses (Quantum
AI Free Zone Campus, Limon; Palo Negro AI & HPC Campus, Bagaces) including carbon, heat
reuse, water, land and frontier-model training over dark fibre.

Usage:
    python secadores_model.py --era5 <ERA5 folder>  # ERA5 2010-2025 (descargar_era5_costa_rica.py output)
    python secadores_model.py                       # fallback climatology (no weather files)

All inputs are in assumptions.json. Results: outputs/*.json, outputs/*.csv.
Standard library + numpy + networkx only.
"""
from __future__ import annotations

import argparse
import calendar
import copy
import csv
import gzip
import json
import math
from pathlib import Path

import networkx as nx
import numpy as np

HERE = Path(__file__).resolve().parent
DAYS = np.array([calendar.monthrange(2025, m)[1] for m in range(1, 13)], dtype=float)
HOURS = DAYS * 24.0
MONTHS = list(range(1, 13))


# ----------------------------------------------------------------------------- inputs
def load_inputs(path_assump: Path | None = None):
    A = json.loads((path_assump or HERE / "assumptions.json").read_text(encoding="utf-8"))
    sites = json.loads((HERE / "data" / "sites.json").read_text(encoding="utf-8"))
    edges = json.loads((HERE / "data" / "fibre-edges.json").read_text(encoding="utf-8"))
    return A, sites, edges


def haversine_km(a, b):
    R = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(d))


ERA5_DIR: Path | None = None
_ERA5_CACHE: dict = {}
ERA5_FIELDS = ("precipitation", "temperature_2m", "relative_humidity_2m", "shortwave_radiation", "wind_speed_100m", "et0_fao_evapotranspiration")


def era5_slug(site_name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", site_name.lower()).strip("_")


def era5_hourly(folder: Path | None, site_name: str):
    """Hourly ERA5 series (UTC) for one site from descargar_era5_costa_rica.py output, read once and cached.
    Returns dict with 'time' (datetime64[h], UTC) and float arrays for ERA5_FIELDS, or None."""
    if folder is None:
        return None
    key = (str(folder), site_name)
    if key in _ERA5_CACHE:
        return _ERA5_CACHE[key]
    f = Path(folder) / f"{era5_slug(site_name)}_hourly_era5.csv.gz"
    if not f.exists():
        _ERA5_CACHE[key] = None
        return None
    t = []; cols = {k: [] for k in ERA5_FIELDS}
    with gzip.open(f, "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t.append(r["time_utc"][:13])
            for k in ERA5_FIELDS:
                v = r.get(k)
                cols[k].append(float(v) if v not in (None, "") else np.nan)
    out = dict(time=np.array(t, dtype="datetime64[h]"), **{k: np.array(v, dtype=float) for k, v in cols.items()})
    _ERA5_CACHE[key] = out
    return out


def era5_daily_local(folder: Path, site_name: str, years=(2010, 2025)):
    """Daily precipitation totals (mm) in Costa Rica local time (UTC-6) from an ERA5 hourly CSV.
    Only local dates inside the requested years are kept, so the first UTC hours of 1 January
    (which fall on 31 December of the previous year locally) do not create an extra partial year."""
    import datetime as dt
    h = era5_hourly(folder, site_name)
    if h is None:
        return None
    loc = h["time"] - np.timedelta64(6, "h")
    day = loc.astype("datetime64[D]")
    yr = day.astype("datetime64[Y]").astype(int) + 1970
    ok = (yr >= years[0]) & (yr <= years[1]) & np.isfinite(h["precipitation"])
    u, inv = np.unique(day[ok], return_inverse=True)
    tot = np.bincount(inv, weights=h["precipitation"][ok])
    return {dt.date.fromisoformat(str(d)): float(v) for d, v in zip(u, tot)}


def era5_local_monthly_mean(h, field):
    """Mean of an hourly ERA5 field by local calendar month (UTC-6)."""
    loc = h["time"] - np.timedelta64(6, "h")
    m = loc.astype("datetime64[M]").astype(int) % 12
    v = h[field]; ok = np.isfinite(v)
    return np.array([v[ok & (m == i)].mean() for i in range(12)])


def daily_from_rows(rows, years=(2010, 2025)):
    import datetime as dt
    daily = {}
    for r in rows:
        p = r.get("precipitation")
        if p in (None, ""):
            continue
        t = dt.datetime.strptime(r["time_utc"][:13], "%Y-%m-%dT%H") - dt.timedelta(hours=6)
        if not (years[0] <= t.year <= years[1]):
            continue
        k = t.date()
        daily[k] = daily.get(k, 0.0) + float(p)
    return dict(sorted(daily.items()))


def rain_stats_from_daily(daily, days_needed=3, wet_mm=1.0):
    """Mean rain days per month and the directly counted probability that a drying batch started on a
    day of that month finds `days_needed` consecutive dry days (observed temporal ordering preserved)."""
    import datetime as dt
    yrs = sorted({d.year for d in daily})
    rain = np.zeros(12); start_ok = np.zeros(12); start_n = np.zeros(12)
    keys = list(daily)
    for d in keys:
        if daily[d] >= wet_mm:
            rain[d.month - 1] += 1
        run = [d + dt.timedelta(days=k) for k in range(days_needed)]
        if all(x in daily for x in run):
            start_n[d.month - 1] += 1
            if all(daily[x] < wet_mm for x in run):
                start_ok[d.month - 1] += 1
    return dict(rain_days=rain / max(len(yrs), 1), window=start_ok / np.maximum(start_n, 1), years=len(yrs))


def window_probability(rain_days_month, days_needed=3, r=0.3):
    """Climatology fallback: first-order Markov occurrence model with persistence r."""
    p = np.clip(1 - np.asarray(rain_days_month, dtype=float) / DAYS, 0.0, 1.0)
    pdd = p + r * (1 - p)
    return p * pdd ** (days_needed - 1)


# ----------------------------------------------------------------------------- network
def node_it_mw(A, sites):
    """IT MW per site: proportional to installed hydro capacity (sizing mode 'hydro_share') or by scale class."""
    N = A["network"]; Z = N.get("sizing", {})
    if Z.get("mode") == "hydro_share":
        tot = sum(s["hydro_mw"] for s in sites)
        raw = {s["id"]: max(Z["min_it_mw"], Z["total_it_mw"] * s["hydro_mw"] / tot) for s in sites}
        k = Z["total_it_mw"] / sum(raw.values())
        return {i: round(v * k, 2) for i, v in raw.items()}
    return {s["id"]: N["it_mw_by_scale"][s["scale"]] for s in sites}


def scale_label(mw):
    return "hub" if mw >= 20 else ("medium" if mw >= 5 else "small")


def build_network(A, sites, edges, era5: Path | None = None, scale_it: float = 1.0):
    N = A["network"]
    nodes = []
    itmap = node_it_mw(A, sites)
    for s in sites:
        sid = str(s["id"])
        zone = A["climate_zone"][sid]
        rd = None; win = None; t_air = None; rh_air = None
        if era5 is not None:
            dl = era5_daily_local(era5, f"{s['id']:02d} {s['name']}")
            if dl:
                st = rain_stats_from_daily(dl, A["drying"]["sun_drying"]["days_needed"], A["drying"]["sun_drying"].get("wet_mm", 1.0))
                rd, win = st["rain_days"], st["window"]
            hh = era5_hourly(era5, f"{s['id']:02d} {s['name']}")
            if hh is not None:
                t_air = float(np.nanmean(hh["temperature_2m"])); rh_air = float(np.nanmean(hh["relative_humidity_2m"]))
        if rd is None:
            rd = np.array(A["rain_days_default"][zone], dtype=float)
        nodes.append(dict(
            id=s["id"], name=s["name"], lat=s["lat"], lon=s["lon"], hydro_mw=s["hydro_mw"],
            operator=s["operator"], region=s["region"], scale=scale_label(itmap[s["id"]]), role=s["role"],
            it_mw=itmap[s["id"]] * scale_it,
            regime=A["site_regime"][sid], zone=zone, rain_days=np.asarray(rd, dtype=float), sun_window=win,
            rain_source="ERA5" if (era5 is not None and rd is not None and not np.array_equal(rd, A["rain_days_default"][zone])) else "default",
            era5_t_air_c=t_air, era5_rh_pct=rh_air,
            metro=("metropolitano" in s["role"]),
            aqua=(s["id"] in A["aquaculture"]["nodes"]),
        ))
    G = nx.Graph()
    by = {n["id"]: n for n in nodes}
    for n in nodes:
        G.add_node(n["id"])
    for a, b in edges:
        km = haversine_km((by[a]["lat"], by[a]["lon"]), (by[b]["lat"], by[b]["lon"])) * N["fibre_route_factor"]
        G.add_edge(a, b, km=km, lat_ms=km * N["light_us_per_km"] / 1000.0)
    return nodes, G


def permission_matrix(A, nodes, case: str):
    """Monthly allowed fraction of IT capacity per node. case: normal | dry_year | firm | seasonal."""
    P = A["ice_permission_profiles"]
    M = np.zeros((len(nodes), 12))
    for i, n in enumerate(nodes):
        prof = np.array(P[n["regime"]], dtype=float)
        if case == "firm":
            prof = np.ones(12)
        elif case == "seasonal":
            prof = np.array(P["seasonal_climate_optimised"], dtype=float)
        elif case == "dry_year":
            prof = prof.copy()
            for m in P["dry_months"]:
                prof[m - 1] = prof[m - 1] * P["dry_year_multiplier_dry_months"]
        M[i] = prof
    return M


def grid_factors(A):
    g = A["grid_carbon"]
    th = g["thermal_kg_per_kwh"]
    out = {
        "avg_2025": np.full(12, (1 - g["average_2025_renewable_share"]) * th),
        "avg_2024": np.full(12, (1 - g["average_2024_renewable_share"]) * th),
    }
    for key, shares in (("marg_normal", g["marginal_thermal_share_normal"]), ("marg_dry_year", g["marginal_thermal_share_dry_year"])):
        f = np.full(12, shares["wet"] * th)
        for m in g["dry_months"]:
            f[m - 1] = shares["dry"] * th
        for m in g["shoulder_months"]:
            f[m - 1] = shares["shoulder"] * th
        out[key] = f
    return out


def carbon_sensitivity(A, comp_fn):
    """Marginal-share sensitivity: thermal shares scaled, and a flat (non-seasonal) marginal share with the same annual mean."""
    out = {}
    g = A["grid_carbon"]
    for sc in g["marginal_sensitivity_scales"]:
        A2 = copy.deepcopy(A)
        for key in ("marginal_thermal_share_normal",):
            A2["grid_carbon"][key] = {k: min(1.0, v * sc) for k, v in g[key].items()}
        out[f"scale_{sc}"] = comp_fn(A2)
    A3 = copy.deepcopy(A)
    f = grid_factors(A)["marg_normal"]; mean_share = float((f * DAYS).sum() / DAYS.sum() / g["thermal_kg_per_kwh"])
    A3["grid_carbon"]["marginal_thermal_share_normal"] = {"dry": mean_share, "shoulder": mean_share, "wet": mean_share}
    out["flat"] = comp_fn(A3)
    return out


# ----------------------------------------------------------------------------- drying
def product_yields(p):
    e, w0, w1 = p["edible_fraction"], p["moisture_fresh"], p["moisture_dried"]
    dried = e * (1 - w0) / (1 - w1)
    water = e - dried
    return dried, water


def drying_kwh_per_kg(A, eff="central"):
    D = A["drying"]
    return D["latent_kwh_per_kg"] / D["dryer_thermal_efficiency"][eff]


def _ras_heat(vol, makeup_frac, dT, Q):
    makeup_kwh = vol * makeup_frac * 365 * 1.163 * dT
    area = 1.5 * vol / Q["tank_depth_m"]
    loss_kwh = Q["ua_w_per_m2_k"] * area * dT * 8760 / 1000.0
    return (makeup_kwh + loss_kwh) / 1000.0


def host_population(A):
    """Population of the host districts (each district counted once)."""
    D = json.loads((HERE / A["community"]["districts_file"]).read_text(encoding="utf-8"))
    return float(sum(D["population_2022"].values()))


def seafood_gift(A):
    """Community seafood allocation (t/yr whole weight) by species, produced on top of the market tonnage."""
    Q = A["aquaculture"]; G = Q.get("community_seafood", {})
    if not G.get("enabled"):
        return dict(population=0.0, total_t=0.0, camaron_t=0.0, snapper_t=0.0)
    pop = host_population(A)
    tot = pop * G["kg_per_person_year"] / 1000.0
    nc, ns = Q["national_camaron_t"], Q["national_snapper_t"]
    return dict(population=pop, total_t=tot, camaron_t=tot * nc / (nc + ns), snapper_t=tot * ns / (nc + ns))


def seafood_gift_cost(A):
    """Cash production cost of the community seafood (waste heat free): feed, seed, RAS electricity, labour, salt and
    annualised RAS capital, plus its value at domestic prices."""
    Q = A["aquaculture"]; G = Q["community_seafood"]; Sx = Q["snapper_ras"]; E = A["economics"]
    g = seafood_gift(A)
    lab = A["jobs"]["ras_fte_per_100_t"] * E["staff_usd_per_fte"] / 100000.0
    cap = G["ras_capex_usd_per_kg_year"] * crf(E["commercial_conservative"]["wacc"], G["ras_life_years"])
    salt_c = Q["makeup_fraction_per_day"] * 365 / (Q["stocking_kg_per_m3_harvest"] * Q["cycles_per_year"]) * Q["camaron_salt_kg_per_m3"] * Q["salt_usd_per_kg"]
    salt_s = Sx["makeup_fraction_per_day"] * 365 / (Sx["stocking_kg_per_m3_harvest"] * Sx["cycles_per_year"]) * Sx["salt_kg_per_m3"] * Q["salt_usd_per_kg"]
    tariff = A["drying"]["electricity_tariff_usd_per_kwh"]
    per_kg_c = dict(feed=Q["fcr_camaron"] * G["camaron_feed_usd_per_kg_feed"], seed=G["camaron_seed_usd_per_kg"],
                    electricity=Q["ras_kwh_e_per_kg"] * tariff, labour=lab, salt=salt_c, capital=cap)
    per_kg_s = dict(feed=Q["snapper_fcr"] * G["snapper_feed_usd_per_kg_feed"], seed=G["snapper_seed_usd_per_kg"],
                    electricity=Sx["ras_kwh_e_per_kg"] * tariff, labour=lab, salt=salt_s, capital=cap)
    cost = g["camaron_t"] * 1000 * sum(per_kg_c.values()) + g["snapper_t"] * 1000 * sum(per_kg_s.values())
    value = g["camaron_t"] * 1000 * Q["camaron_price_usd_kg"] + g["snapper_t"] * 1000 * Sx["price_usd_kg"]
    return dict(g, cost_per_kg_camaron=per_kg_c, cost_per_kg_snapper=per_kg_s, cost_usd=cost, retail_value_usd=value,
                cost_per_person_usd=cost / g["population"] if g["population"] else 0.0,
                capex_usd=(g["camaron_t"] + g["snapper_t"]) * 1000 * G["ras_capex_usd_per_kg_year"])


def aquaculture(A, nodes):
    """Camaron (low-salinity RAS) and spotted rose snapper (low-exchange marine RAS) per node.
    Sizing 'national_multiple': each species' total = multiple x national production, shared in proportion to node IT load."""
    Q = A["aquaculture"]
    res = {}
    aqn = [n for n in nodes if n["aqua"]]
    itsum = sum(n["it_mw"] for n in aqn) or 1.0
    Sx = Q.get("snapper_ras", {})
    for n in aqn:
        if Q.get("sizing") == "national_multiple":
            gift = seafood_gift(A)
            t = (Q["national_multiple"] * Q["national_camaron_t"] + gift["camaron_t"]) * n["it_mw"] / itsum
            ts = (Q["national_multiple"] * Q["national_snapper_t"] + gift["snapper_t"]) * n["it_mw"] / itsum if Sx else 0.0
        elif Q.get("sizing") == "per_mw_it":
            t = Q["camaron_t_per_mw_it"] * n["it_mw"]; ts = 0.0
        else:
            t = Q["camaron_t_per_node"]; ts = 0.0
        t *= Q.get("_cam_mult", 1.0)
        vol = t * 1000.0 / (Q["stocking_kg_per_m3_harvest"] * Q["cycles_per_year"])
        amb = n["era5_t_air_c"] if (Q.get("ambient_source") == "era5_air_mean" and n.get("era5_t_air_c") is not None) \
            else Q["node_ambient_water_c"].get(str(n["id"]), 24.0)
        dT = max(Q["water_temp_c"] - amb, 0.0)
        heat_c = _ras_heat(vol, Q["makeup_fraction_per_day"], dT, Q)
        mk_c = vol * Q["makeup_fraction_per_day"] * 365
        heat_s = 0.0; vol_s = 0.0; mk_s = 0.0; dTs = 0.0
        if ts > 0:
            vol_s = ts * 1000.0 / (Sx["stocking_kg_per_m3_harvest"] * Sx["cycles_per_year"])
            dTs = max(Sx["water_temp_c"] - amb, 0.0)
            heat_s = _ras_heat(vol_s, Sx["makeup_fraction_per_day"], dTs, Q)
            mk_s = vol_s * Sx["makeup_fraction_per_day"] * 365
        salt_t = (mk_c * Q.get("camaron_salt_kg_per_m3", 0.0) + mk_s * Sx.get("salt_kg_per_m3", 0.0)) / 1000.0
        heat_mwh = heat_c + heat_s
        res[n["id"]] = dict(t=t, snapper_t=ts, volume_m3=vol, snapper_volume_m3=vol_s, dT=dT, ambient_c=amb,
                            heat_camaron_mwh=heat_c, heat_snapper_mwh=heat_s, heat_mwh=heat_mwh,
                            heat_kwh_per_kg=heat_mwh * 1000 / ((t + ts) * 1000) if (t + ts) else 0.0,
                            makeup_m3=mk_c + mk_s, salt_t=salt_t,
                            elec_mwh=t * Q["ras_kwh_e_per_kg"] + ts * Sx.get("ras_kwh_e_per_kg", 0.0))
    return res


def circular_loop(A, camaron_t_total, snapper_case: str):
    Q = A["aquaculture"]
    snap_t = Q["snapper_cases_t"][snapper_case] if snapper_case in Q["snapper_cases_t"] else float(snapper_case)
    # demands (t protein from fishmeal)
    snap_feed = snap_t * Q["snapper_fcr"]
    snap_fm_protein = snap_feed * Q["snapper_diet_fishmeal_fraction"] * Q["fishmeal_protein"]
    cam_feed = camaron_t_total * Q["fcr_camaron"]
    cam_fm_protein = cam_feed * Q["camaron_diet_fishmeal_fraction"] * Q["fishmeal_protein"]
    # by-product supplies
    snap_byp = snap_t * (1 - Q["snapper_fillet_yield"])
    snap_meal = snap_byp * Q["snapper_meal_yield_per_kg_byproduct"]
    snap_meal_protein = snap_meal * Q["snapper_meal_protein"]
    cam_byp = camaron_t_total * Q["processed_share"] * Q["camaron_byproduct_fraction_processed"]
    cam_meal = cam_byp * Q["camaron_meal_yield_per_kg_byproduct"]
    cam_meal_protein = cam_meal * Q["camaron_meal_protein"]
    # cross-species allocation (no intra-species recycling)
    to_snap_protein = min(cam_meal_protein, snap_fm_protein * Q["max_fishmeal_protein_replacement_snapper_diet"])
    to_cam_protein = min(snap_meal_protein, cam_fm_protein * Q["max_fishmeal_protein_replacement_camaron_diet"])
    water_per_kg_byp = 1 - (1 - Q["byproduct_moisture"]) / (1 - Q["meal_moisture"])
    kwh = drying_kwh_per_kg(A)
    return dict(
        snapper_t=snap_t, camaron_t=camaron_t_total,
        snapper_feed_t=snap_feed, camaron_feed_t=cam_feed,
        snapper_fishmeal_protein_t=snap_fm_protein, camaron_fishmeal_protein_t=cam_fm_protein,
        snapper_byproduct_t=snap_byp, snapper_meal_t=snap_meal, snapper_meal_protein_t=snap_meal_protein,
        camaron_byproduct_t=cam_byp, camaron_meal_t=cam_meal, camaron_meal_protein_t=cam_meal_protein,
        camaron_meal_to_snapper_protein_t=to_snap_protein,
        snapper_meal_to_camaron_protein_t=to_cam_protein,
        snapper_fishmeal_protein_replaced_pct=100 * to_snap_protein / snap_fm_protein if snap_fm_protein else 0,
        camaron_fishmeal_protein_replaced_pct=100 * to_cam_protein / cam_fm_protein if cam_fm_protein else 0,
        snapper_meal_surplus_protein_t=snap_meal_protein - to_cam_protein,
        camaron_meal_surplus_protein_t=cam_meal_protein - to_snap_protein,
        meal_drying_heat_mwh=(snap_byp + cam_byp) * water_per_kg_byp * kwh,
        fishmeal_avoided_t=(to_snap_protein + to_cam_protein) / Q["fishmeal_protein"],
    )


# ----------------------------------------------------------------------------- core run
def dryer_modes(A, eff="central"):
    """kWh per kg of water evaporated for each dryer technology."""
    D = A["drying"]; H = D["heat_pump"]
    open_heat = drying_kwh_per_kg(A, eff)
    return dict(open=dict(heat=open_heat, elec=D["fan_kwh_e_per_kg_water"], condensate=0.0),
                hp=dict(heat=H["dc_heat_kwh_per_kg"], elec=1.0 / H["smer_kg_per_kwh"], condensate=H["condensate_recovery"]))


def product_table(A, cam_total, loop_case):
    """Drying products, adding the cross-species meal stream from the camaron-snapper loop."""
    P = copy.deepcopy(A["drying"]["products"])
    L = circular_loop(A, cam_total, loop_case)
    Q = A["aquaculture"]
    P["harinas"] = dict(edible_fraction=1.0, moisture_fresh=Q["byproduct_moisture"], moisture_dried=Q["meal_moisture"],
                        price_bulk_usd_kg=Q["meal_value_usd_kg"], price_premium_usd_kg=Q["meal_value_usd_kg"],
                        processing_usd_per_kg_dried=Q["meal_processing_usd_kg"], feed_price_usd_per_kg_fresh=0.0,
                        national_fresh_t=L["snapper_byproduct_t"] + L["camaron_byproduct_t"], available_fraction=1.0,
                        months=list(range(1, 13)), nodes=Q["meal_nodes"], priority=5, retail_water=False, category="pienso acuícola")
    return P


def run_network(A, nodes, perm_case="normal", eff="central", price="bulk", avail_mult=1.0, cam_mult=1.0,
                capacity_case=False, dryer_mode="hybrid", loop_case=None, gift=True, util_mult=1.0):
    N = A["network"]
    D = A["drying"]
    loop_case = loop_case or A["aquaculture"]["central_loop_case"]
    perm = permission_matrix(A, nodes, perm_case)
    it_mw = np.array([n["it_mw"] for n in nodes])
    it_mwh = it_mw[:, None] * N["it_utilisation"] * util_mult * perm * HOURS[None, :]
    fac_mwh = it_mwh * N["pue"]
    heat_mwh = it_mwh * N["recoverable_heat_fraction_of_it"]
    heat_left = heat_mwh.copy()
    A2 = copy.deepcopy(A)
    if not gift and "community_seafood" in A2["aquaculture"]:
        A2["aquaculture"]["community_seafood"]["enabled"] = False  # community seafood not produced when unfunded
    A2["aquaculture"]["camaron_t_per_node"] = A["aquaculture"]["camaron_t_per_node"] * cam_mult
    A2["aquaculture"]["_cam_mult"] = cam_mult if A["aquaculture"].get("sizing") == "per_mw_it" else 1.0
    aq = aquaculture(A2, nodes)
    ras_heat = np.zeros_like(heat_mwh)
    for i, n in enumerate(nodes):
        if n["id"] in aq:
            need = aq[n["id"]]["heat_mwh"] * DAYS / DAYS.sum()
            got = np.minimum(need, heat_left[i])
            ras_heat[i] = got
            heat_left[i] -= got
    M = dryer_modes(A, eff)
    snap_nodes = sum(v.get("snapper_t", 0.0) for v in aq.values())
    lc = snap_nodes if (loop_case == "nodes_ras" and snap_nodes > 0) else loop_case
    products = product_table(A2, sum(v["t"] for v in aq.values()), lc)
    order = sorted(products, key=lambda k: products[k]["priority"])
    dry_heat = np.zeros_like(heat_mwh); dry_elec = np.zeros_like(heat_mwh)
    condensate = np.zeros_like(heat_mwh); condensate_retail_ok = np.zeros_like(heat_mwh)
    prod_out = {}
    fee_open = D["dryer_capex_usd_per_tonne_water_per_year"] + D["dryer_om_usd_per_tonne_water"] + D["fan_kwh_e_per_kg_water"] * 1000 * D["electricity_tariff_usd_per_kwh"]
    Hp = D["heat_pump"]
    fee_hp = Hp["capex_usd_per_tonne_water_per_year"] + D["dryer_om_usd_per_tonne_water"] + M["hp"]["elec"] * 1000 * D["electricity_tariff_usd_per_kwh"]
    hp_quota = D["distilled_water"]["retail_cap_m3_per_year"] / Hp["condensate_recovery"]  # t water for 'hybrid'
    for pname in order:
        p = products[pname]
        mode = dryer_mode
        f_hp = 0.0
        if dryer_mode == "food_hp":
            mode = "hp_all" if p.get("retail_water", False) else "heat_first"
        elif dryer_mode == "hybrid":
            mode = "heat_first"
            if p.get("retail_water", False) and hp_quota > 0:
                dy, wy = product_yields(p)
                wtot = p["national_fresh_t"] * p["available_fraction"] * avail_mult * wy
                f_hp = min(1.0, hp_quota / wtot) if wtot else 0.0
                hp_quota -= f_hp * wtot
        f_open = (p.get("dryer_capex_override", D["dryer_capex_usd_per_tonne_water_per_year"]) + D["dryer_om_usd_per_tonne_water"]
                  + D["fan_kwh_e_per_kg_water"] * 1000 * D["electricity_tariff_usd_per_kwh"])
        dried_y, water_y = product_yields(p)
        fresh_total = p["national_fresh_t"] * p["available_fraction"] * (avail_mult if pname != "harinas" else 1.0)
        fresh_m = np.zeros(12)
        for m in p["months"]:
            fresh_m[m - 1] = fresh_total / len(p["months"])
        if "nodes" in p:
            elig = [i for i, n in enumerate(nodes) if n["id"] in p["nodes"]]
        else:
            elig = [i for i, n in enumerate(nodes) if n["zone"] in p["zones"] and not (n["metro"] and n["id"] != 19)]
        w_open = np.zeros((len(nodes), 12)); w_hp = np.zeros((len(nodes), 12))
        for mi in range(12):
            remaining = fresh_m[mi]
            if remaining <= 0 or not elig:
                continue
            if f_hp > 0:  # dedicated heat-pump share (hybrid design), spread by node IT size
                wts = np.array([nodes[i]["it_mw"] for i in elig], dtype=float); wts /= wts.sum()
                for k, i in enumerate(elig):
                    w = f_hp * remaining * wts[k] * water_y
                    w_hp[i, mi] += w
                    need_h = w * M["hp"]["heat"]
                    got = min(need_h, max(heat_left[i, mi], 0.0))
                    heat_left[i, mi] -= got
                    dry_heat[i, mi] += got
                    dry_elec[i, mi] += w * M["hp"]["elec"] + (need_h - got) / Hp["booster_cop"]
                remaining *= (1 - f_hp)
            if mode in ("open", "heat_first"):
                for _ in range(6):
                    caps = np.array([max(heat_left[i, mi], 0.0) for i in elig]) / M["open"]["heat"] / water_y  # t fresh
                    if caps.sum() <= 1e-9 or remaining <= 1e-9:
                        break
                    take = np.minimum(caps / caps.sum() * remaining, caps)
                    for k, i in enumerate(elig):
                        w = take[k] * water_y
                        w_open[i, mi] += w
                        heat_left[i, mi] -= w * M["open"]["heat"]
                    remaining -= take.sum()
            if (mode == "hp_all" or (mode == "heat_first" and p.get("hp_allowed", True))) and remaining > 1e-9:
                wts = np.array([nodes[i]["it_mw"] for i in elig], dtype=float); wts /= wts.sum()
                for k, i in enumerate(elig):
                    w = remaining * wts[k] * water_y
                    w_hp[i, mi] += w
                    need_h = w * M["hp"]["heat"]
                    got = min(need_h, max(heat_left[i, mi], 0.0))
                    heat_left[i, mi] -= got
                    dry_heat[i, mi] += got
                    dry_elec[i, mi] += w * M["hp"]["elec"] + (need_h - got) / Hp["booster_cop"]
                remaining = 0.0
        dry_heat += w_open * M["open"]["heat"]
        dry_elec += w_open * M["open"]["elec"]
        fresh_proc_m = (w_open + w_hp).sum(axis=0) / water_y
        fresh_proc = fresh_proc_m.sum()
        press = p.get("press_kwh_per_t_fresh", 0.0) * (w_open + w_hp) / water_y / 1000.0  # MWh
        dry_elec += press
        cond = w_hp * M["hp"]["condensate"]
        condensate += cond
        if p.get("retail_water", False):
            condensate_retail_ok += cond
        water_t = (w_open + w_hp).sum(); dried_t = fresh_proc * dried_y
        pr = p["price_bulk_usd_kg"] if price == "bulk" else p["price_premium_usd_kg"]
        Lg = A.get("logistics", {})
        removed_t = fresh_proc * (1 - p["edible_fraction"])
        haul_usd = fresh_proc * Lg.get("haul_km", {}).get(pname, 0.0) * Lg.get("usd_per_t_km", 0.0)
        liquid_usd = removed_t * Lg.get("pretreatment_liquid_usd_per_t", 0.0) if p.get("press_kwh_per_t_fresh", 0.0) > 0 else 0.0
        service_cost = w_open.sum() * f_open + w_hp.sum() * fee_hp + haul_usd + liquid_usd
        if p.get("service_only", False):
            revenue = service_cost * (1 + p.get("service_margin", 0.0))
            costs = service_cost
        else:
            revenue = dried_t * 1000 * pr
            costs = dried_t * 1000 * p["processing_usd_per_kg_dried"] + fresh_proc * 1000 * p["feed_price_usd_per_kg_fresh"] + service_cost
        prod_out[pname] = dict(category=p.get("category", ""), retail=bool(p.get("retail_water", False)),
                               pretreatment_removed_t=removed_t, haul_usd=haul_usd, liquid_disposal_usd=liquid_usd,
                               removed_kind=("press liquid" if p.get("press_kwh_per_t_fresh", 0.0) > 0 else "peel, seed, trimmings"), fresh_available_t=fresh_total, unprocessed_t=fresh_total - fresh_proc, fresh_processed_t=fresh_proc, dried_t=dried_t,
                               water_removed_t=water_t, water_open_t=w_open.sum(), water_hp_t=w_hp.sum(),
                               heat_mwh=float((w_open * M["open"]["heat"]).sum() + min((w_hp * M["hp"]["heat"]).sum(), 1e18)),
                               elec_mwh=float((w_open * M["open"]["elec"] + w_hp * M["hp"]["elec"]).sum() + press.sum()),
                               condensate_t=float(cond.sum()), dried_yield=dried_y, water_per_kg_fresh=water_y,
                               revenue_usd=revenue, costs_usd=costs, gross_margin_usd=revenue - costs,
                               fee_usd_per_t_water=f_open, fee_hp_usd_per_t_water=fee_hp, mode=mode,
                               breakeven_price_usd_kg=((dried_t * 1000 * p["processing_usd_per_kg_dried"] + fresh_proc * 1000 * p["feed_price_usd_per_kg_fresh"] + service_cost) / (dried_t * 1000)) if dried_t else None,
                               monthly_processed_t=fresh_proc_m.tolist(), per_node_fresh_t=((w_open + w_hp).sum(axis=1) / water_y).tolist())
    # distilled-water allocation: retail (capped, treated) -> RAS make-up -> irrigation / process water
    W = D["distilled_water"]
    retail = min(condensate_retail_ok.sum(), W["retail_cap_m3_per_year"])
    Qa = A2["aquaculture"]
    ras_need = sum(v["makeup_m3"] for v in aq.values())
    ras_cond = 0.0
    for i, n in enumerate(nodes):
        if n["id"] in aq:
            ras_cond += min(condensate[i].sum(), aq[n["id"]]["makeup_m3"])
    ras_cond = min(ras_cond, ras_need, condensate.sum() - retail)
    other = condensate.sum() - retail - ras_cond
    water_out = dict(condensate_m3=float(condensate.sum()), retail_eligible_m3=float(condensate_retail_ok.sum()), retail_m3=float(retail),
                     retail_revenue_usd=retail * W["retail_net_usd_per_m3"], retail_treatment_cost_usd=retail * W["treatment_usd_per_m3"],
                     ras_makeup_m3=float(ras_cond), ras_need_m3=float(ras_need), ras_value_usd=ras_cond * W["process_water_value_usd_per_m3"],
                     irrigation_process_m3=float(other), other_value_usd=other * W["irrigation_value_usd_per_m3"])
    latent = sum(v["water_removed_t"] for v in prod_out.values()) * D["latent_kwh_per_kg"]  # MWh
    drying_energy = dry_heat.sum() + dry_elec.sum()
    capacity = None
    if capacity_case:
        cap_heat = heat_mwh.sum() * D["website_capacity_case_dryer_heat_use"]
        capacity = dict(heat_mwh=cap_heat, water_removed_t=cap_heat / M["open"]["heat"])
    reused = ras_heat.sum() + dry_heat.sum()
    return dict(perm=perm, it_mwh=it_mwh, fac_mwh=fac_mwh, heat_mwh=heat_mwh, ras_heat=ras_heat, dry_heat=dry_heat, dry_elec=dry_elec,
                heat_rejected=heat_left, products=prod_out, aq=aq, kwh_per_kg=M["open"]["heat"], modes=M, capacity=capacity,
                distilled_water=water_out, condensate=condensate,
                totals=dict(it_gwh=it_mwh.sum() / 1000, facility_gwh=fac_mwh.sum() / 1000, heat_gwh=heat_mwh.sum() / 1000,
                            ras_heat_gwh=ras_heat.sum() / 1000, drying_heat_gwh=dry_heat.sum() / 1000,
                            drying_elec_gwh=dry_elec.sum() / 1000, rejected_heat_gwh=heat_left.sum() / 1000,
                            reused_heat_gwh=reused / 1000, reused_pct_of_heat=100 * reused / heat_mwh.sum(),
                            erf_pct=100 * reused / fac_mwh.sum(),
                            water_evaporated_t=sum(v["water_removed_t"] for v in prod_out.values()),
                            water_hp_t=sum(v["water_hp_t"] for v in prod_out.values()),
                            dried_t=sum(v["dried_t"] for v in prod_out.values()),
                            drying_energy_efficiency_pct=100 * latent / drying_energy if drying_energy else 0,
                            it_capacity_factor=it_mwh.sum() / (it_mw.sum() * 8760)))


# ----------------------------------------------------------------------------- farmer economics
def farmer_economics(A, nodes, eff="central", r=None):
    D = A["drying"]
    S = D["sun_drying"]
    kwh = drying_kwh_per_kg(A, eff)
    fee_t_water = D["dryer_capex_usd_per_tonne_water_per_year"] + D["dryer_om_usd_per_tonne_water"] + \
        D["fan_kwh_e_per_kg_water"] * 1000 * D["electricity_tariff_usd_per_kwh"]
    lpg_t_water = kwh / D_lpg_eff(A) * 1000 * D["lpg_usd_per_kwh_fuel"]
    zones = sorted({n["zone"] for n in nodes})
    r = S["rain_persistence_r"] if r is None else r
    zone_rd = {}; zone_win = {}
    for z in zones:
        zn = [n for n in nodes if n["zone"] == z]
        zone_rd[z] = np.mean([n["rain_days"] for n in zn], axis=0)
        wins = [n["sun_window"] for n in zn if n.get("sun_window") is not None]
        zone_win[z] = np.mean(wins, axis=0) if wins else window_probability(zone_rd[z], S["days_needed"], r)
    out = []
    for pname, p in D["products"].items():
        if pname not in D["fresh_local_price_usd_kg"]:
            continue
        dried_y, water_y = product_yields(p)
        for z in p["zones"]:
            for mi in range(12):
                pdry = max(0.0, 1 - zone_rd[z][mi] / DAYS[mi])
                f = float(zone_win[z][mi])
                sun_out = dried_y * (1 - S["base_loss"]) * (f + (1 - f) * (1 - S["failed_batch_loss"]))  # t dried per t fresh
                sun_rev = sun_out * 1000 * p["price_bulk_usd_kg"] * S["price_factor_vs_bulk"]
                sun_cost = S["labour_h_per_t_fresh_per_day"] * S["days_needed"] * S["labour_usd_per_h"] + \
                    sun_out * 1000 * p["processing_usd_per_kg_dried"] * S["processing_usd_per_kg_dried_fraction"]
                sd_out = dried_y * 0.98
                sd_rev = sd_out * 1000 * p["price_bulk_usd_kg"]
                sd_cost = sd_out * 1000 * p["processing_usd_per_kg_dried"] + water_y * fee_t_water
                lpg_cost = sd_cost + water_y * lpg_t_water
                out.append(dict(product=pname, zone=z, month=mi + 1, p_dry_day=pdry, sun_feasibility=f,
                                fresh_sale_usd_t=D["fresh_local_price_usd_kg"][pname] * 1000,
                                sun_net_usd_t=sun_rev - sun_cost, secadores_net_usd_t=sd_rev - sd_cost,
                                lpg_net_usd_t=sd_rev - lpg_cost,
                                secadores_fee_usd_t_fresh=water_y * fee_t_water,
                                lpg_fuel_usd_t_fresh=water_y * lpg_t_water))
    return out


def D_lpg_eff(A):
    return A["grid_carbon"]["lpg_burner_efficiency"]


# ----------------------------------------------------------------------------- comparators
def wind_power_curve(v, W):
    """Generic pitch-regulated turbine curve normalised to rated power (cubic between cut-in and rated)."""
    vi, vr, vo = W["cut_in_ms"], W["rated_ms"], W["cut_out_ms"]
    v = np.asarray(v, dtype=float)
    return np.where(v < vi, 0.0, np.where(v < vr, (v ** 3 - vi ** 3) / (vr ** 3 - vi ** 3), np.where(v < vo, 1.0, 0.0)))


def wind_calibration(A, h):
    """Single wind-speed scaling factor k so that the ERA5-driven capacity factor in the calibration years equals the
    observed pooled capacity factor of the Costa Rican wind fleet (CENCE annual reports). Bisection, no SciPy."""
    W = A["comparators"]["palo_negro_bagaces"]["era5_wind"]
    yr = h["time"].astype("datetime64[Y]").astype(int) + 1970
    obs = W["observed_fleet"]
    pooled = sum(o["gwh"] for o in obs) / sum(o["mw"] * (8784 if o["year"] % 4 == 0 else 8760) / 1000 for o in obs)
    m = np.isin(yr, [o["year"] for o in obs]) & np.isfinite(h["wind_speed_100m"])
    v = h["wind_speed_100m"][m]
    lo, hi = 0.5, 5.0
    for _ in range(80):
        k = 0.5 * (lo + hi)
        if wind_power_curve(k * v, W).mean() < pooled:
            lo = k
        else:
            hi = k
    k = 0.5 * (lo + hi)
    per_year = {}
    for o in obs:
        mm = (yr == o["year"]) & np.isfinite(h["wind_speed_100m"])
        per_year[str(o["year"])] = dict(observed_cf=o["gwh"] / (o["mw"] * (8784 if o["year"] % 4 == 0 else 8760) / 1000),
                                        modelled_cf=float(wind_power_curve(k * h["wind_speed_100m"][mm], W).mean()))
    raw_cf = float(np.nanmean(wind_power_curve(h["wind_speed_100m"], W)))
    return dict(k=k, pooled_observed_cf=pooled, raw_era5_cf=raw_cf, per_year=per_year)


def pv_output_per_mw_ac(A, h):
    """Fixed-tilt PV AC output per MW_AC from ERA5 global horizontal irradiance and 2-m air temperature."""
    P = A["comparators"]["palo_negro_bagaces"]["era5_pv"]
    g = np.nan_to_num(h["shortwave_radiation"]); t = np.nan_to_num(h["temperature_2m"], nan=25.0)
    tc = t + g * (P["noct_c"] - 20.0) / 800.0
    dc = g / 1000.0 * (1 + P["gamma_per_k"] * (tc - 25.0)) * P["performance_ratio"]
    return np.clip(dc * P["dc_ac_ratio"], 0.0, 1.0)


def palo_negro_hourly(A, it_mw):
    """Palo Negro own PV + wind + battery, hourly. With ERA5 files: real 2010-2025 hourly weather at the Bagaces proxy,
    wind bias-corrected to the observed Costa Rican fleet; results are means over the years, with the interannual range."""
    C = A["comparators"]["palo_negro_bagaces"]
    h = era5_hourly(ERA5_DIR, C["era5_site"]) if ERA5_DIR is not None else None
    if h is None:
        return palo_negro_hourly_synthetic(A, it_mw)
    load = it_mw * C["pue"] * C["utilisation"]
    cal = wind_calibration(A, h)
    wind = C["wind_mw"] * wind_power_curve(cal["k"] * np.nan_to_num(h["wind_speed_100m"]), C["era5_wind"])
    pv = C["pv_mw"] * pv_output_per_mw_ac(A, h)
    loc = h["time"] - np.timedelta64(6, "h")
    yr = loc.astype("datetime64[Y]").astype(int) + 1970
    mo = loc.astype("datetime64[M]").astype(int) % 12
    years = sorted(set(int(y) for y in yr if 2010 <= y <= 2025 and (yr == y).sum() >= 8700))
    sq = math.sqrt(C["battery_rte"])
    soc = C["battery_mwh"] * 0.5
    n = len(pv)
    grid_h = np.zeros(n); ren_h = np.zeros(n); curt_h = np.zeros(n)
    for i in range(n):
        gen = pv[i] + wind[i]
        if gen >= load:
            ren_h[i] = load
            surplus = gen - load
            ch = min(surplus, C["battery_mw"], (C["battery_mwh"] - soc) / sq)
            soc += ch * sq
            curt_h[i] = surplus - ch
        else:
            deficit = load - gen
            dis = min(deficit, C["battery_mw"], soc * sq)
            soc -= dis / sq
            ren_h[i] = gen + dis
            grid_h[i] = deficit - dis
    per_year = []
    grid_m = np.zeros(12); pv_m = np.zeros(12); wind_m = np.zeros(12); curt = 0.0; ren = 0.0
    for y in years:
        sel = yr == y
        nh = sel.sum()
        gm = np.array([grid_h[sel & (mo == i)].sum() for i in range(12)])
        grid_m += gm; curt += curt_h[sel].sum(); ren += ren_h[sel].sum()
        pv_m += np.array([pv[sel & (mo == i)].sum() for i in range(12)])
        wind_m += np.array([wind[sel & (mo == i)].sum() for i in range(12)])
        per_year.append(dict(year=y, renewable_share=float(ren_h[sel].sum() / (load * nh)), grid_gwh=float(grid_h[sel].sum() / 1000),
                             wind_cf=float(wind[sel].sum() / (C["wind_mw"] * nh)), pv_cf=float(pv[sel].sum() / (C["pv_mw"] * nh)),
                             dry_season_grid_gwh=float(gm[[0, 1, 2, 3]].sum() / 1000)))
    ny = len(years)
    grid_m /= ny; pv_m /= ny; wind_m /= ny; curt /= ny; ren /= ny
    total = load * 8760
    shares = [p["renewable_share"] for p in per_year]
    return dict(load_mw=load, facility_mwh=total, grid_mwh=grid_m, renewable_used_mwh=ren,
                monthly_pv_gwh=(pv_m / 1000).tolist(), monthly_wind_gwh=(wind_m / 1000).tolist(),
                monthly_grid_gwh=(grid_m / 1000).tolist(), monthly_load_gwh=(load * HOURS / 1000).tolist(),
                curtailed_or_export_mwh=curt, pv_mwh=pv_m.sum(), wind_mwh=wind_m.sum(),
                hourly_renewable_share=float(np.mean(shares)), annual_generation_ratio=(pv_m.sum() + wind_m.sum()) / total,
                weather_source="ERA5 2010-2025 hourly (wind bias-corrected)", years=years, per_year=per_year,
                renewable_share_range=[float(min(shares)), float(max(shares))],
                wind_cf=float(np.mean([p["wind_cf"] for p in per_year])), wind_cf_range=[float(min(p["wind_cf"] for p in per_year)), float(max(p["wind_cf"] for p in per_year))],
                pv_cf=float(np.mean([p["pv_cf"] for p in per_year])), pv_cf_range=[float(min(p["pv_cf"] for p in per_year)), float(max(p["pv_cf"] for p in per_year))],
                monthly_wind_cf=[float(wind_m[i] / (C["wind_mw"] * HOURS[i])) for i in range(12)],
                monthly_pv_cf=[float(pv_m[i] / (C["pv_mw"] * HOURS[i])) for i in range(12)],
                wind_calibration=cal)


def palo_negro_hourly_synthetic(A, it_mw):
    C = A["comparators"]["palo_negro_bagaces"]
    load = it_mw * C["pue"] * C["utilisation"]
    pvi = np.array(A["pv_monthly_index_guanacaste"]); pvi = pvi / pvi.mean()
    wdi = np.array(A["wind_monthly_index_guanacaste"]); wdi = wdi / wdi.mean()
    hours = []
    for mi in range(12):
        for d in range(int(DAYS[mi])):
            for h in range(24):
                hours.append((mi, h))
    shape = np.array([max(0.0, math.sin(math.pi * (h - 6) / 12)) if 6 <= h <= 18 else 0.0 for h in range(24)])
    shape_mean = shape.mean()
    soc = C["battery_mwh"] * 0.5
    grid = np.zeros(12); ren_used = np.zeros(12); curtailed = np.zeros(12); pv_gen = np.zeros(12); wind_gen = np.zeros(12)
    for mi, h in hours:
        pv = C["pv_mw"] * C["pv_cf"] * pvi[mi] * shape[h] / shape_mean
        wd = C["wind_mw"] * C["wind_cf"] * wdi[mi] * (1.10 if 10 <= h <= 18 else 0.92)
        pv = min(pv, C["pv_mw"]); wd = min(wd, C["wind_mw"])
        pv_gen[mi] += pv; wind_gen[mi] += wd
        gen = pv + wd
        if gen >= load:
            ren_used[mi] += load
            surplus = gen - load
            ch = min(surplus, C["battery_mw"], (C["battery_mwh"] - soc) / math.sqrt(C["battery_rte"]))
            soc += ch * math.sqrt(C["battery_rte"])
            curtailed[mi] += surplus - ch
        else:
            ren_used[mi] += gen
            deficit = load - gen
            dis = min(deficit, C["battery_mw"], soc * math.sqrt(C["battery_rte"]))
            soc -= dis / math.sqrt(C["battery_rte"])
            ren_used[mi] += dis
            grid[mi] += deficit - dis
    total = load * 8760
    return dict(load_mw=load, facility_mwh=total, grid_mwh=grid, renewable_used_mwh=ren_used.sum(),
                monthly_pv_gwh=(pv_gen / 1000).tolist(), monthly_wind_gwh=(wind_gen / 1000).tolist(),
                monthly_grid_gwh=(grid / 1000).tolist(), monthly_load_gwh=(load * HOURS / 1000).tolist(),
                curtailed_or_export_mwh=curtailed.sum(), pv_mwh=pv_gen.sum(), wind_mwh=wind_gen.sum(),
                hourly_renewable_share=ren_used.sum() / total, annual_generation_ratio=(pv_gen.sum() + wind_gen.sum()) / total)


def carbon_t(monthly_grid_mwh, factors):
    return {k: float((monthly_grid_mwh * f).sum()) for k, f in factors.items()}  # MWh*kg/kWh = t


def compare_systems(A, nodes, G, base_run, firm_run, dry_run, scaled_run, seasonal_run):
    F = grid_factors(A)
    out = {}
    def metrics(name, it_mwh_m, fac_mwh_m, grid_mwh_m, reused_mwh, water_m3, land_ha, it_mw, notes):
        it = it_mwh_m.sum(); fac = fac_mwh_m.sum()
        c = carbon_t(grid_mwh_m, F)
        return dict(name=name, it_mw=it_mw, it_gwh=it / 1000, facility_gwh=fac / 1000, grid_gwh=grid_mwh_m.sum() / 1000,
                    pue=fac / it if it else None, reused_heat_gwh=reused_mwh / 1000, erf=reused_mwh / fac if fac else 0,
                    ere=(fac - reused_mwh) / it if it else None, cooling_water_m3=water_m3,
                    wue_l_per_kwh_it=water_m3 * 1000 / (it * 1000) if it else None, land_ha=land_ha,
                    carbon_t=c, cue_g_per_kwh_it={k: v * 1e6 / (it * 1000) for k, v in c.items()},
                    dry_season_share_of_grid=float(grid_mwh_m[[0, 1, 2, 3]].sum() / grid_mwh_m.sum()) if grid_mwh_m.sum() else 0,
                    dry_season_grid_gwh=float(grid_mwh_m[[0, 1, 2, 3]].sum() / 1000),
                    monthly_grid_gwh_all=(grid_mwh_m / 1000).tolist(),
                    notes=notes)
    L = A["land"]
    def sd_land_parts(run):
        dried_water = sum(p["water_removed_t"] for p in run["products"].values())
        cam = sum(v["t"] + v.get("snapper_t", 0.0) for v in run["aq"].values())
        return dict(computing=sum(n["it_mw"] for n in nodes) * L["dc_ha_per_mw"], drying=dried_water / 1000 * L["dryer_ha_per_1000_t_water"],
                    aquaculture=cam / 100 * L["ras_ha_per_100_t"])
    def sd_land(run):
        dried_water = sum(p["water_removed_t"] for p in run["products"].values())
        cam = sum(v["t"] + v.get("snapper_t", 0.0) for v in run["aq"].values())
        return sum(n["it_mw"] for n in nodes) * L["dc_ha_per_mw"] + dried_water / 1000 * L["dryer_ha_per_1000_t_water"] + cam / 100 * L["ras_ha_per_100_t"]
    for key, run, label in (("secadores_normal", base_run, "Secadores Digitales, ICE interruptible (normal year)"),
                            ("secadores_dry_year", dry_run, "Secadores Digitales, ICE interruptible (dry year)"),
                            ("secadores_seasonal", seasonal_run, "Secadores Digitales, rainy-season-led (climate-optimised)"),
                            ("secadores_firm", firm_run, "Secadores Digitales, firm supply"),
                            ("secadores_200mw", scaled_run, "Secadores Digitales scaled to 200 MW IT (normal year)")):
        reused = run["ras_heat"].sum() + run["dry_heat"].sum()
        it_mw = float(sum(n["it_mw"] for n in nodes)) * (200.0 / sum(n["it_mw"] for n in nodes) if key == "secadores_200mw" else 1.0)
        out[key] = metrics(label, run["it_mwh"].sum(axis=0), run["fac_mwh"].sum(axis=0), run["fac_mwh"].sum(axis=0),
                           reused, 0.0, sd_land(run) * (200.0 / sum(n["it_mw"] for n in nodes) if key == "secadores_200mw" else 1), it_mw,
                           "closed-loop liquid cooling + dry coolers; grid supply from co-located hydro plant contract")
        Q = A["aquaculture"]; J = A["jobs"]; Gc = A["grid_carbon"]
        cam = sum(v["t"] + v.get("snapper_t", 0.0) for v in run["aq"].values())
        dried = sum(p["dried_t"] for p in run["products"].values())
        out[key]["ras_makeup_water_m3"] = sum(v["makeup_m3"] for v in run["aq"].values())
        out[key]["fruit_water_evaporated_t"] = sum(p["water_removed_t"] for p in run["products"].values())
        out[key]["dried_food_t"] = dried
        out[key]["camaron_t"] = cam
        out[key]["jobs_fte"] = dict(data_centre=it_mw * J["dc_fte_per_mw"], drying=sum(p["dried_t"] for p in run["products"].values() if p.get("retail", False)) / 1000 * J["drying_fte_per_1000_t_dried"]
                                    + sum(p["dried_t"] for p in run["products"].values() if not p.get("retail", False)) / 1000 * J["drying_fte_per_1000_t_bulk"],
                                    aquaculture=cam / 100 * J["ras_fte_per_100_t"])
        w_tot = sum(p["water_removed_t"] for p in run["products"].values())
        lpg_gross = w_tot * run["kwh_per_kg"] / Gc["lpg_burner_efficiency"] * Gc["lpg_kg_co2_per_kwh_fuel"]  # t CO2 (t water * kWh/kg = MWh)
        Fm = grid_factors(A)
        de = run["dry_elec"].sum(axis=0)
        out[key]["lpg_drying_co2_avoided_if_counterfactual_t"] = lpg_gross
        out[key]["drying_elec_co2_t"] = {k: float((de * f).sum()) for k, f in Fm.items()}
        out[key]["lpg_drying_co2_avoided_net_t"] = {k: lpg_gross - float((de * f).sum()) for k, f in Fm.items()}
    for key, run in (("secadores_normal", base_run), ("secadores_seasonal", seasonal_run), ("secadores_firm", firm_run), ("secadores_dry_year", dry_run)):
        parts = sd_land_parts(run)
        out[key]["land_direct_ha"] = sum(parts.values()); out[key]["land_parts_ha"] = parts
        out[key]["land_new_generation_ha"] = 0.0
        out[key]["cooling_water_basis"] = "zero: closed loop with dry coolers"
    Qc = A["comparators"]["quantum_limon"]
    it_m = Qc["it_mw"] * Qc["utilisation"] * HOURS
    fac_m = it_m * Qc["pue"]
    out["quantum_limon"] = metrics("Quantum AI Free Zone Campus (Limón)", it_m, fac_m, fac_m, 0.0,
                                   Qc["water_l_s"] / 1000 * 3600 * 8760, Qc["land_ha"], Qc["it_mw"],
                                   "firm ICE grid; 230-kV substation; on-site thermal backup; 350 L/s water")
    out["quantum_limon"]["land_direct_ha"] = Qc["land_ha"]; out["quantum_limon"]["land_new_generation_ha"] = 0.0
    Pq = permission_matrix(A, nodes[:1], "seasonal")[0]
    it_q = Qc["it_mw"] * Qc["utilisation"] * Pq * HOURS
    out["quantum_limon_seasonal"] = metrics("Quantum (Limón), rainy-season-led (matched schedule)", it_q, it_q * Qc["pue"], it_q * Qc["pue"], 0.0,
                                            0.0, Qc["land_ha"], Qc["it_mw"], "same seasonal permission profile as the network")
    out["quantum_limon"]["cooling_water_basis"] = "declared municipal-water availability of 350 L/s (upper bound, not metered consumption); wells additional"
    Pc = A["comparators"]["palo_negro_bagaces"]
    for key, itmw in (("palo_negro_38mw", Pc["it_mw"]), ("palo_negro_120mw", Pc["it_mw_alt"])):
        h = palo_negro_hourly(A, itmw)
        it_m = itmw * Pc["utilisation"] * HOURS
        fac_m = it_m * Pc["pue"]
        land = Pc["pv_mw"] * Pc["pv_ha_per_mw"] + Pc["wind_mw"] * Pc["wind_ha_direct_per_mw"] + itmw * L["dc_ha_per_mw"]
        m = metrics(f"Palo Negro AI & HPC Campus ({itmw:.0f} MW IT)", it_m, fac_m, h["grid_mwh"], 0.0, 0.0, land, itmw,
                    "own 80 MW PV + 40 MW wind + battery (assumed 160 MWh); ICE backup; closed-loop geothermal-ground cooling")
        m["land_direct_ha"] = itmw * L["dc_ha_per_mw"]
        m["land_new_generation_ha"] = Pc["pv_mw"] * Pc["pv_ha_per_mw"] + Pc["wind_mw"] * Pc["wind_ha_direct_per_mw"]
        m["cooling_water_basis"] = "zero declared (closed geothermal loop)"
        m["own_renewable_hourly_share"] = h["hourly_renewable_share"]
        m["own_generation_to_load_ratio"] = h["annual_generation_ratio"]
        m["own_curtailed_or_export_gwh"] = h["curtailed_or_export_mwh"] / 1000
        for k in ("weather_source", "renewable_share_range", "wind_cf", "wind_cf_range", "pv_cf", "pv_cf_range",
                  "monthly_wind_cf", "monthly_pv_cf", "wind_calibration", "per_year"):
            if k in h:
                m[k] = h[k]
        for k in ("monthly_pv_gwh", "monthly_wind_gwh", "monthly_grid_gwh", "monthly_load_gwh"):
            m[k] = h[k]
        out[key] = m
    return out


# ----------------------------------------------------------------------------- training
def training(A, nodes, G, perm_by_case: dict):
    C = A["compute"]; N = A["network"]
    bw_tbps = N["fibre_pairs_per_edge"] * N["dwdm_channels_per_pair"] * N["gbps_per_channel"] / 1000.0
    bw_bytes = bw_tbps * 1e12 / 8
    # latency: ring through Euler tour of a minimum spanning tree (by km)
    T = nx.minimum_spanning_tree(G, weight="km")
    tour = list(nx.dfs_preorder_nodes(T, source=29))
    ring_lat_ms = 0.0
    for a, b in zip(tour, tour[1:] + tour[:1]):
        ring_lat_ms += nx.shortest_path_length(G, a, b, weight="lat_ms")
    diam_ms = max(nx.single_source_dijkstra_path_length(G, s, weight="lat_ms")[t] for s in G for t in G)
    fibre_km = sum(d["km"] for _, _, d in G.edges(data=True))
    n_sites = len(nodes)
    results = {"inter_site_bandwidth_tbps": bw_tbps, "ring_latency_ms": ring_lat_ms, "max_one_way_latency_ms": diam_ms,
               "fibre_route_km": fibre_km, "fibre_edges": G.number_of_edges(),
               "fibre_capex_usd": [fibre_km * c for c in N["fibre_cost_usd_per_km"]], "systems": {}}
    def flops_per_s(it_mw, gen):
        g = C[gen]
        racks = it_mw * 1000 / (g["rack_kw"] * (1 + C["non_rack_it_overhead"]))
        return racks, racks * g["fp8_dense_ef_per_rack"] * 1e18
    systems = {
        "secadores_net_normal": (sum(n["it_mw"] for n in nodes), perm_by_case["normal"], n_sites),
        "secadores_net_dry_year": (sum(n["it_mw"] for n in nodes), perm_by_case["dry_year"], n_sites),
        "secadores_net_seasonal": (sum(n["it_mw"] for n in nodes), perm_by_case["seasonal"], n_sites),
        "secadores_200mw_normal": (200.0, perm_by_case["normal"], n_sites),
        "quantum_200mw": (200.0, None, 1),
        "palo_negro_38mw": (38.0, None, 1),
        "palo_negro_120mw": (120.0, None, 1),
    }
    for gen in ("gb300_nvl72", "vera_rubin_nvl144"):
        for key, (it_mw, perm, sites_n) in systems.items():
            racks, peak = flops_per_s(it_mw, gen)
            if perm is None:
                monthly_frac = np.full(12, 0.90)
            else:
                w = np.array([n["it_mw"] for n in nodes])
                monthly_frac = 0.90 * (perm * w[:, None]).sum(axis=0) / w.sum()
            eff = peak * C["mfu"]
            # multi-site overhead with DiLoCo-style outer synchronisation
            step_flop = 6 * C["model_params"] * C["tokens_per_step"]
            t_step = step_flop / (eff * float(monthly_frac.mean()) / 0.90)
            overheads = {}
            for H in C["diloco_inner_steps"]:
                if sites_n == 1:
                    overheads[H] = 0.0
                    continue
                bytes_sync = C["model_params"] * (2.0 if H == 1 else C["pseudo_gradient_bytes_per_param"])
                t_comm = 2 * (sites_n - 1) / sites_n * bytes_sync / bw_bytes + ring_lat_ms / 1000 * 2
                overheads[H] = t_comm / (H * t_step)
            ov = overheads[100]
            monthly_flop = eff * monthly_frac * HOURS * 3600 / (1 + ov)
            annual = monthly_flop.sum()
            # months to target starting in June (start of rainy season) and in January
            def months_to(start):
                cum = 0.0
                for k in range(120):
                    mi = (start - 1 + k) % 12
                    if cum + monthly_flop[mi] >= C["target_training_flop"]:
                        return k + (C["target_training_flop"] - cum) / monthly_flop[mi]
                    cum += monthly_flop[mi]
                return float("inf")
            results["systems"][f"{key}|{gen}"] = dict(it_mw=it_mw, racks=racks, gpus=racks * C[gen]["gpus_per_rack"],
                                                      peak_fp8_ef=peak / 1e18, step_time_s=t_step, overhead_by_H=overheads,
                                                      annual_training_flop=annual,
                                                      months_to_target_start_june=months_to(6), months_to_target_start_jan=months_to(1))
    return results


def training_scale_across(A, nodes, G, perm_by_case: dict):
    """Fully synchronous data-parallel training across all sites (gradient all-reduce every step) over the dark-fibre
    ring, with off-the-shelf Ethernet or Spectrum-XGS link efficiency, the fibre pairs needed, and the effect of
    interruptible power (strict: all sites must run; elastic: curtailed sites drop out)."""
    C = A["compute"]; N = A["network"]; X = C["scale_across"]
    T = nx.minimum_spanning_tree(G, weight="km")
    tour = list(nx.dfs_preorder_nodes(T, source=29))
    ring_lat_s = sum(nx.shortest_path_length(G, a, b, weight="lat_ms") for a, b in zip(tour, tour[1:] + tour[:1])) / 1000.0
    n = len(nodes); edges = G.number_of_edges()
    pair_bytes = N["dwdm_channels_per_pair"] * N["gbps_per_channel"] * 1e9 / 8
    base_pairs = N["fibre_pairs_per_edge"]
    w = np.array([x["it_mw"] for x in nodes]); it_mw = w.sum()
    step_flop = 6 * C["model_params"] * C["tokens_per_step"]
    grad_bytes = C["model_params"] * X["gradient_bytes_per_param"]
    pair_edge_cost = 2 * N["dwdm_channels_per_pair"] * X["optics_usd_per_400g_end"] + X["line_system_usd_per_pair_edge"]
    def t_comm(pairs, eta):
        return 2 * (n - 1) / n * grad_bytes / (pairs * pair_bytes * eta) + 2 * ring_lat_s
    out = dict(ring_latency_ms=ring_lat_s * 1000, edges=edges, base_pairs=base_pairs, gradient_tb=grad_bytes / 1e12, systems={})
    for gen in ("gb300_nvl72", "vera_rubin_nvl144"):
        g = C[gen]
        racks = it_mw * 1000 / (g["rack_kw"] * (1 + C["non_rack_it_overhead"]))
        eff = racks * g["fp8_dense_ef_per_rack"] * 1e18 * C["mfu"]
        t_step = step_flop / eff
        def ovh(pairs, eta):
            return max(0.0, t_comm(pairs, eta) - X["compute_comm_overlap"] * t_step) / t_step
        need = next((P for P in range(base_pairs, X["max_fibre_pairs"] + 1) if ovh(P, X["link_efficiency_spectrum_xgs"]) <= X["target_exposed_overhead"]), None)
        need_off = next((P for P in range(base_pairs, X["max_fibre_pairs"] + 1) if ovh(P, X["link_efficiency_off_the_shelf"]) <= X["target_exposed_overhead"]), None)
        res = dict(step_time_s=t_step, comm_time_xgs_base_s=t_comm(base_pairs, X["link_efficiency_spectrum_xgs"]),
                   overhead_off_the_shelf_base=ovh(base_pairs, X["link_efficiency_off_the_shelf"]),
                   overhead_xgs_base=ovh(base_pairs, X["link_efficiency_spectrum_xgs"]),
                   pairs_needed_xgs=need, pairs_needed_off_the_shelf=need_off,
                   overhead_xgs_needed=ovh(need, X["link_efficiency_spectrum_xgs"]) if need else None,
                   extra_optics_capex_usd=(need - base_pairs) * edges * pair_edge_cost if need else None, cases={})
        P = need or X["max_fibre_pairs"]
        o = ovh(P, X["link_efficiency_spectrum_xgs"])
        for case in ("normal", "seasonal", "dry_year"):
            perm = perm_by_case[case]
            avail = {"strict": 0.90 * perm.min(axis=0), "elastic": 0.90 * (perm * w[:, None]).sum(axis=0) / w.sum()}
            r = {}
            for mode, frac in avail.items():
                monthly = eff * frac * HOURS * 3600 / (1 + o)
                cum = 0.0; months = float("inf")
                for k in range(120):
                    mi = (5 + k) % 12
                    if cum + monthly[mi] >= C["target_training_flop"]:
                        months = k + (C["target_training_flop"] - cum) / monthly[mi]; break
                    cum += monthly[mi]
                r[mode] = dict(annual_flop=float(monthly.sum()), months_to_target_start_june=months,
                               full_months=int((frac >= 0.90 - 1e-9).sum()), mean_availability=float(frac.mean() / 0.90))
            res["cases"][case] = r
        # joint sensitivity: MFU x overlap x link efficiency -> fibre pairs needed and months to target (normal, strict)
        S = X.get("sensitivity", {})
        grid = []
        for mfu in S.get("mfu", []):
            for ov_ in S.get("overlap", []):
                for eta in S.get("link_efficiency", []):
                    eff_s = racks * g["fp8_dense_ef_per_rack"] * 1e18 * mfu
                    ts = step_flop / eff_s
                    oh = lambda P: max(0.0, t_comm(P, eta) - ov_ * ts) / ts
                    Pn = next((P for P in range(base_pairs, X["max_fibre_pairs"] + 1) if oh(P) <= X["target_exposed_overhead"]), None)
                    Pu = Pn or X["max_fibre_pairs"]
                    frac = 0.90 * perm_by_case["normal"].min(axis=0)
                    monthly = eff_s * frac * HOURS * 3600 / (1 + oh(Pu))
                    cum = 0.0; months = float("inf")
                    for k in range(120):
                        mi = (5 + k) % 12
                        if cum + monthly[mi] >= C["target_training_flop"]:
                            months = k + (C["target_training_flop"] - cum) / monthly[mi]; break
                        cum += monthly[mi]
                    grid.append(dict(mfu=mfu, overlap=ov_, link_efficiency=eta, pairs_needed=Pn, months_strict=months))
        pn = [x["pairs_needed"] for x in grid if x["pairs_needed"]]
        res["sensitivity"] = dict(grid=grid, pairs_min=min(pn) if pn else None, pairs_max=max(pn) if pn else None,
                                  any_infeasible=any(x["pairs_needed"] is None for x in grid),
                                  months_min=min(x["months_strict"] for x in grid), months_max=max(x["months_strict"] for x in grid))
        out["systems"][gen] = res
    return out


def aquaculture_accounts(A, run_aq):
    """Commercial aquaculture account (market tonnage only) with the same unit cash costs as the community seafood."""
    Q = A["aquaculture"]; Sx = Q["snapper_ras"]
    gc = seafood_gift_cost(A)
    g = seafood_gift(A) if Q.get("community_seafood", {}).get("enabled") else dict(camaron_t=0.0, snapper_t=0.0)
    cam = sum(v["t"] for v in run_aq.values()); snp = sum(v.get("snapper_t", 0.0) for v in run_aq.values())
    cam_m = Q["national_multiple"] * Q["national_camaron_t"]; snp_m = Q["national_multiple"] * Q["national_snapper_t"]
    imp = 2086.0
    sales = imp * 1000 * Q["camaron_price_usd_kg"] + (cam_m - imp) * 1000 * Q["camaron_price_export_usd_kg"] + snp_m * 1000 * Sx["price_usd_kg"]
    cost = cam_m * 1000 * sum(gc["cost_per_kg_camaron"].values()) + snp_m * 1000 * sum(gc["cost_per_kg_snapper"].values())
    gift_export_rev = gc["camaron_t"] * 1000 * Q["camaron_price_export_usd_kg"] + gc["snapper_t"] * 1000 * Sx["price_usd_kg"]
    return dict(market_camaron_t=cam_m, market_snapper_t=snp_m, sales_usd=sales, cash_cost_usd=cost, margin_usd=sales - cost,
                gift_cost_usd=gc["cost_usd"], gift_if_exported_revenue_usd=gift_export_rev,
                gift_if_exported_margin_usd=gift_export_rev - gc["cost_usd"],
                produced_camaron_t=cam, produced_snapper_t=snp, gift_produced=(cam - cam_m) > 1e-6)


def integrated_balance(A, nodes, run, perm_case, comm_case):
    """Integrated project boundary: data-centre facility + drying + RAS + EV charging (if the programme is funded),
    with marginal carbon; and continuity of the critical RAS loads during IT curtailment."""
    F = grid_factors(A); I = A["integrated"]; Cm = A["community"]
    fac_m = run["fac_mwh"].sum(axis=0); dry_m = run["dry_elec"].sum(axis=0)
    ras_e = sum(v["elec_mwh"] for v in run["aq"].values()); ras_m = np.full(12, ras_e) * DAYS / DAYS.sum()
    ev_on = bool(comm_case and not comm_case.get("suspended", False))
    ev_m = (np.full(12, Cm["ev_km_per_year"] * Cm["ev_kwh_per_km"] * (sum(json.loads((HERE / Cm["districts_file"]).read_text(encoding="utf-8"))["population_2022"].values()) / Cm["persons_per_household"]) / 1000.0) * DAYS / DAYS.sum()) if ev_on else np.zeros(12)
    tot_m = fac_m + dry_m + ras_m + ev_m
    carbon = {k: float((tot_m * f).sum()) for k, f in F.items()}  # t CO2 (MWh x kg/kWh)
    carbon_dc = {k: float((fac_m * f).sum()) for k, f in F.items()}
    # continuity: RAS heat needed in curtailed hours (IT fully off for the non-permitted fraction of hours)
    perm = permission_matrix(A, nodes, perm_case)
    need_curt_m = np.zeros(12); vol = 0.0; heat_need = 0.0
    for i, n in enumerate(nodes):
        a = run["aq"].get(n["id"])
        if not a:
            continue
        need_m = a["heat_mwh"] * DAYS / DAYS.sum()
        need_curt_m += need_m * (1 - perm[i])
        vol += a["volume_m3"] + a.get("snapper_volume_m3", 0.0); heat_need += a["heat_mwh"]
    need_curt = float(need_curt_m.sum())
    mean_mw = heat_need / 8760.0
    hours_per_k = vol * 1.163 / 1000.0 / mean_mw if mean_mw else float("inf")  # MWh per K of tank water / MW of heat demand
    backup_e = need_curt / I["heat_pump_backup_cop"]
    return dict(facility_gwh=fac_m.sum() / 1000, drying_elec_gwh=dry_m.sum() / 1000, ras_elec_gwh=ras_e / 1000, ev_charging_gwh=ev_m.sum() / 1000,
                integrated_gwh=tot_m.sum() / 1000, integrated_over_dc_pct=100 * (tot_m.sum() / fac_m.sum() - 1),
                carbon_integrated_t=carbon, carbon_dc_t=carbon_dc,
                ras_heat_in_curtailed_hours_gwh=need_curt / 1000, ras_mean_heat_mw=mean_mw, ras_tank_volume_m3=vol,
                tank_inertia_hours_per_k=hours_per_k, backup_heat_pump_elec_gwh=backup_e / 1000,
                backup_heat_pump_mw=mean_mw / I["heat_pump_backup_cop"],
                backup_cost_usd=backup_e * 1000 * A["economics"]["electricity_usd_per_kwh"],
                backup_co2_t={k: float((need_curt_m / I["heat_pump_backup_cop"] * f).sum()) for k, f in F.items()},
                ras_critical_mw=ras_e / 8760.0)


# ----------------------------------------------------------------------------- sensitivity
def sensitivity(A, nodes):
    base = run_network(A, nodes)
    def margin(r):
        return sum(p["gross_margin_usd"] for p in r["products"].values())
    b = margin(base)
    cases = [
        ("Feedstock availability ×0.5 / ×2", dict(avail_mult=0.5), dict(avail_mult=2.0)),
        ("Bulk vs premium dried price", dict(), dict(price="premium")),
    ]
    out = []
    A3 = copy.deepcopy(A)
    for k in ("dryer_capex_usd_per_tonne_water_per_year", "dryer_om_usd_per_tonne_water"):
        A3["drying"][k] *= 1.5
    A4 = copy.deepcopy(A)
    for k in ("dryer_capex_usd_per_tonne_water_per_year", "dryer_om_usd_per_tonne_water"):
        A4["drying"][k] *= 0.5
    A5 = copy.deepcopy(A); A5["drying"]["heat_pump"]["capex_usd_per_tonne_water_per_year"] *= 1.5
    A6 = copy.deepcopy(A); A6["drying"]["heat_pump"]["capex_usd_per_tonne_water_per_year"] *= 0.5
    out.append(dict(label="Heat-pump dryer capital ±50%", low=margin(run_network(A5, nodes)) - b, high=margin(run_network(A6, nodes)) - b))
    A7 = copy.deepcopy(A); A7["drying"]["heat_pump"]["smer_kg_per_kwh"] = A["drying"]["heat_pump"]["smer_range"][0]
    A8 = copy.deepcopy(A); A8["drying"]["heat_pump"]["smer_kg_per_kwh"] = A["drying"]["heat_pump"]["smer_range"][1]
    out.append(dict(label="Heat-pump SMER 2–4 kg/kWh", low=margin(run_network(A7, nodes)) - b, high=margin(run_network(A8, nodes)) - b))
    out.append(dict(label="Dryer capital and O&M ±50%", low=margin(run_network(A3, nodes)) - b, high=margin(run_network(A4, nodes)) - b))
    for label, lo, hi in cases:
        out.append(dict(label=label, low=margin(run_network(A, nodes, **lo)) - b, high=margin(run_network(A, nodes, **hi)) - b))
    # processing-cost and feed-price sensitivities (±30%)
    for key, label in (("processing_usd_per_kg_dried", "Processing cost ±30%"), ("feed_price_usd_per_kg_fresh", "Feedstock price ±30%"),
                       ("price_bulk_usd_kg", "Bulk dried price ±30%")):
        vals = []
        for f in ((0.7, 1.3) if key == "price_bulk_usd_kg" else (1.3, 0.7)):
            A2 = copy.deepcopy(A)
            for p in A2["drying"]["products"].values():
                p[key] *= f
            vals.append(margin(run_network(A2, nodes)) - b)
        out.append(dict(label=label, low=vals[0], high=vals[1]))
    return b, out


def dryer_designs(A, nodes):
    """Compare dryer technology strategies on thermal-efficiency metrics (normal year)."""
    out = {}
    for d in ("open", "hybrid", "food_hp", "hp_all"):
        r = run_network(A, nodes, dryer_mode=d)
        T = r["totals"]; W = r["distilled_water"]
        margin = sum(p["gross_margin_usd"] for p in r["products"].values())
        water_val = W["retail_revenue_usd"] - W["retail_treatment_cost_usd"] + W["ras_value_usd"] + W["other_value_usd"]
        drying_in = T["drying_heat_gwh"] + T["drying_elec_gwh"]
        out[d] = dict(T, margin_usd=margin, water_value_usd=water_val, condensate_m3=W["condensate_m3"], retail_m3=W["retail_m3"],
                      kg_water_per_kwh_input=T["water_evaporated_t"] / (drying_in * 1000) if drying_in else 0,
                      kg_water_per_kwh_elec=T["water_evaporated_t"] / (T["drying_elec_gwh"] * 1000) if T["drying_elec_gwh"] else 0,
                      unprocessed_t=sum(p["unprocessed_t"] for p in r["products"].values()),
                      fresh_processed_t=sum(p["fresh_processed_t"] for p in r["products"].values()))
    return out


def smer_sensitivity(A, nodes):
    out = []
    lo, hi = A["drying"]["heat_pump"]["smer_range"]
    for s in (lo, A["drying"]["heat_pump"]["smer_kg_per_kwh"], hi):
        A2 = copy.deepcopy(A); A2["drying"]["heat_pump"]["smer_kg_per_kwh"] = s
        r = run_network(A2, nodes)
        out.append(dict(smer=s, margin_usd=sum(p["gross_margin_usd"] for p in r["products"].values()), **r["totals"]))
    caps = []
    for c in (1000.0, 3000.0, 10000.0, 30000.0):
        A2 = copy.deepcopy(A); A2["drying"]["distilled_water"]["retail_cap_m3_per_year"] = c
        W = run_network(A2, nodes)["distilled_water"]
        caps.append(dict(cap_m3=c, retail_m3=W["retail_m3"], net_usd=W["retail_revenue_usd"] - W["retail_treatment_cost_usd"]))
    return dict(smer=out, retail_cap=caps)


# ----------------------------------------------------------------------------- compute economics and community benefits
def economics(A, nodes, comp, fibre_capex_usd, price_case="central", capex_case="central"):
    """Annual P&L per system for GB300-class GPUs sold as reserved GPU-hours (US$)."""
    E = A["economics"]; C = A["compute"]["gb300_nvl72"]; J = A["jobs"]
    kw_per_gpu = C["rack_kw"] * (1 + A["compute"]["non_rack_it_overhead"]) / C["gpus_per_rack"]
    price = E["gpu_hour_price_usd"][price_case]
    rack_cost = E["rack_capex_usd"][capex_case]
    fac_cost = E["facility_capex_usd_per_mw_it"][capex_case]
    out = {}
    for key, c in comp.items():
        it_mw = c["it_mw"]
        racks = it_mw * 1000 / (C["rack_kw"] * (1 + A["compute"]["non_rack_it_overhead"]))
        gpus = racks * C["gpus_per_rack"]
        gpu_h = c["it_gwh"] * 1e6 / kw_per_gpu
        rev = gpu_h * price
        if key.startswith("palo_negro"):
            own = (c["facility_gwh"] - c["grid_gwh"]) * 1e6
            elec = c["grid_gwh"] * 1e6 * E["electricity_usd_per_kwh"] + own * E["palo_negro_own_lcoe_usd_per_kwh"]
        else:
            elec = c["facility_gwh"] * 1e6 * E["electricity_usd_per_kwh"]
        it_capex = racks * rack_cost
        fac_capex = it_mw * fac_cost
        fib = fibre_capex_usd * (it_mw / sum(n["it_mw"] for n in nodes)) if key.startswith("secadores") else 0.0
        capex = it_capex + fac_capex + fib
        staff = it_mw * J["dc_fte_per_mw"] * E["staff_usd_per_fte"]
        maint = it_capex * E["maintenance_frac_it_capex"]
        ins = capex * E["insurance_frac_capex"]
        netops = it_mw * E["network_ops_usd_per_mw"] + fib * E["fibre_om_frac"]
        water = c.get("cooling_water_m3", 0.0) * E.get("water_usd_per_m3", 1.5) if E.get("charge_declared_water", False) else 0.0
        opex = elec + staff + maint + ins + netops + water
        ebitda = rev - opex
        refresh = it_capex * (1 - E["it_residual_fraction"]) / E["it_life_years"]
        fac_dep = (fac_capex + fib) / E["facility_life_years"]
        out[key] = dict(it_mw=it_mw, racks=racks, gpus=gpus, gpu_hours=gpu_h, utilisation_of_gpu_hours=gpu_h / (gpus * 8760),
                        revenue_usd=rev, electricity_usd=elec, staff_usd=staff, maintenance_usd=maint, insurance_usd=ins,
                        network_usd=netops, water_usd=water, opex_usd=opex, ebitda_usd=ebitda, ebitda_margin=ebitda / rev,
                        it_capex_usd=it_capex, facility_capex_usd=fac_capex, fibre_capex_usd=fib, capex_usd=capex,
                        refresh_reserve_usd=refresh, facility_depreciation_usd=fac_dep,
                        cash_after_refresh_usd=ebitda - refresh, community_10pct_usd=E["community_share_of_ebitda"] * ebitda,
                        ebitda_per_mw_usd=ebitda / it_mw, payback_years=capex / (ebitda - refresh) if ebitda > refresh else float("inf"),
                        capital_charge_wacc_usd=it_capex * crf(E["commercial_conservative"]["wacc"], E["it_life_years"]) + (fac_capex + fib) * crf(E["commercial_conservative"]["wacc"], E["facility_life_years"]))
        out[key]["ebitda_less_capital_charge_usd"] = ebitda - out[key]["capital_charge_wacc_usd"]
        out[key]["water_upper_bound_usd"] = c.get("cooling_water_m3", 0.0) * E.get("water_usd_per_m3", 1.5)
        Cc = out[key]["capital_charge_wacc_usd"]; sh = E["community_share_of_ebitda"]
        out[key]["price_for_full_community_usd_h"] = (Cc / (1 - sh) + opex) / gpu_h if gpu_h else None
        out[key]["price_for_zero_margin_usd_h"] = (Cc + opex) / gpu_h if gpu_h else None
        distributable = out[key]["ebitda_less_capital_charge_usd"]  # central case: free-zone income-tax exemption assumed
        out[key]["community_funded_usd"] = min(out[key]["community_10pct_usd"], max(0.0, distributable))
        out[key]["community_suspended"] = out[key]["community_funded_usd"] <= 0.0
        out[key]["headroom_after_community_usd"] = distributable - out[key]["community_funded_usd"]
        out[key]["community_share_of_headroom"] = out[key]["community_10pct_usd"] / distributable if distributable > 0 else float("inf")
    return out


def crf(r, n):
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


def economics_conservative(A, econ_central):
    """Commercial-risk case: declining GPU-hour prices over the hardware life, a discount for interruptible supply,
    partial contracting of permitted GPU-hours, capital charged at the WACC and corporate income tax."""
    E = A["economics"]; K = E["commercial_conservative"]
    n = E["it_life_years"]; d = K["gpu_price_decline_per_year"]
    price_factor = sum((1 - d) ** k for k in range(n)) / n
    out = {}
    for key, e in econ_central.items():
        interruptible = key.startswith("secadores") and key != "secadores_firm"
        disc = K["interruption_discount"] if interruptible else 0.0
        rev = e["revenue_usd"] * price_factor * (1 - disc) * K["sold_fraction"]
        opex = e["opex_usd"] - e["electricity_usd"] * (1 - K["sold_fraction"])
        ebitda = rev - opex
        cap_charge = (e["it_capex_usd"] * crf(K["wacc"], n) + (e["facility_capex_usd"] + e["fibre_capex_usd"]) * crf(K["wacc"], E["facility_life_years"]))
        dep = e["it_capex_usd"] / n + (e["facility_capex_usd"] + e["fibre_capex_usd"]) / E["facility_life_years"]
        tax = max(0.0, (ebitda - dep) * K["tax_rate"])
        comm = E["community_share_of_ebitda"] * max(ebitda, 0.0)
        distributable = ebitda - cap_charge - tax
        funded = min(comm, max(0.0, distributable))
        out[key] = dict(price_factor=price_factor, interruption_discount=disc, revenue_usd=rev, ebitda_usd=ebitda,
                        capital_charge_usd=cap_charge, tax_usd=tax, community_10pct_usd=comm,
                        distributable_usd=distributable, community_funded_usd=funded, community_suspended=funded <= 0.0,
                        free_cash_after_capital_tax_community_usd=ebitda - cap_charge - tax - comm,
                        free_cash_after_funded_community_usd=distributable - funded)
    return out


def ev_timeline(budget_full, ramp, cost, charging):
    """Years to fund `cost` with a deployment ramp; charging is paid first each year (scaled by ramp)."""
    if budget_full - charging <= 0:
        return float("inf")
    cum = 0.0
    for y in range(1, 60):
        f = ramp[min(y, len(ramp)) - 1]
        avail = f * budget_full - f * charging
        if cum + avail >= cost:
            return y - 1 + (cost - cum) / avail
        cum += avail
    return float("inf")


def community(A, nodes, econ):
    """Host-district communities and EV benefit options funded by 10% of EBITDA."""
    Cm = A["community"]; E = A["economics"]
    D = json.loads((HERE / Cm["districts_file"]).read_text(encoding="utf-8"))
    pop = D["population_2022"]
    # each district counted once; its households are shared among the nodes it hosts in proportion to IT MW
    hosts = {}
    for n in nodes:
        for dname in D["nodes"][str(n["id"])]:
            hosts.setdefault(dname, []).append(n)
    per_node = {n["id"]: dict(pop=0.0, households=0.0, districts=D["nodes"][str(n["id"])]) for n in nodes}
    for dname, ns in hosts.items():
        w = sum(x["it_mw"] for x in ns)
        for x in ns:
            per_node[x["id"]]["pop"] += pop[dname] * x["it_mw"] / w
            per_node[x["id"]]["households"] += pop[dname] / Cm["persons_per_household"] * x["it_mw"] / w
    P = sum(pop.values()); HH = P / Cm["persons_per_household"]
    kwh_ev = Cm["ev_km_per_year"] * Cm["ev_kwh_per_km"]
    out = dict(population=P, households=HH, districts=len(pop), per_node=per_node,
               ev_kwh_per_year=kwh_ev, charging_gwh=HH * kwh_ev / 1e6, cases={})
    for case in ("secadores_normal", "secadores_seasonal", "secadores_firm"):
        target = econ[case]["community_10pct_usd"]
        budget = econ[case].get("community_funded_usd", target)
        charging = HH * kwh_ev * E["electricity_usd_per_kwh"]
        gift = seafood_gift_cost(A)["cost_usd"] if A["aquaculture"].get("community_seafood", {}).get("enabled") else 0.0
        gift_paid = min(gift, max(budget, 0.0))
        r = dict(budget_usd=budget, target_usd=target, suspended=budget <= 0.0, budget_per_household_usd=budget / HH, charging_usd=charging, options={},
                 seafood_cost_usd=gift, seafood_paid_usd=gift_paid, seafood_funded=gift_paid >= gift - 1e-6 and gift > 0,
                 ev_budget_usd=budget - gift_paid)
        budget = budget - gift_paid
        for pc in ("low", "central", "high"):
            ev = Cm["ev_price_usd"][pc]
            for label, frac in (("free_ev", 1.0), ("half_price", 0.5)):
                cost = HH * ev * frac
                r["options"][f"{label}|{pc}"] = dict(cost_usd=cost, years_with_charging=cost / (budget - charging) if budget > charging else float("inf"),
                                                     years_without_charging=cost / budget if budget > 0 else float("inf"))
        # steady state after the first EV: replacement every 10 years + free charging
        r["steady_state_usd"] = HH * Cm["ev_price_usd"]["central"] / 10 + charging
        r["steady_state_share_of_budget"] = r["steady_state_usd"] / budget if budget > 0 else float("inf")
        out["cases"][case] = r
    comp = {}
    for key, dd in D["comparators"].items():
        p = sum(dd.values()); hh = p / Cm["persons_per_household"]
        ek = {"quantum_limon": "quantum_limon", "palo_negro_bagaces": "palo_negro_120mw"}[key]
        b = econ[ek]["community_10pct_usd"]
        comp[key] = dict(population=p, households=hh, hypothetical_budget_usd=b, per_household_usd=b / hh,
                         years_free_ev=hh * Cm["ev_price_usd"]["central"] / b,
                         districts=list(dd))
        if key == "palo_negro_bagaces":
            b38 = econ["palo_negro_38mw"]["community_10pct_usd"]
            comp[key]["hypothetical_budget_38mw_usd"] = b38; comp[key]["per_household_38mw_usd"] = b38 / hh
    out["comparators"] = comp
    return out


def clusters(A, nodes, G, perm):
    """Regional dark-fibre clusters, each training a smaller frontier model (cluster_target_flop)."""
    C = A["compute"]; N = A["network"]
    groups = {"norte_guanacaste": [n["id"] for n in nodes if n["zone"] in ("ZN", "PN")] + [19],
              "central_los_santos": [n["id"] for n in nodes if n["zone"] == "VC"] + [32],
              "reventazon_caribe": [n["id"] for n in nodes if n["zone"] == "CA"]}
    bw_bytes = N["fibre_pairs_per_edge"] * N["dwdm_channels_per_pair"] * N["gbps_per_channel"] * 1e9 / 8
    w = {n["id"]: n["it_mw"] for n in nodes}
    idx = {n["id"]: i for i, n in enumerate(nodes)}
    target = C["cluster_target_flop"]
    params = math.sqrt(target / 120.0)  # compute-optimal: 20 tokens per parameter, 6ND
    res = {}
    for name, ids in groups.items():
        H = G.subgraph(ids)
        assert nx.is_connected(H), name
        T = nx.minimum_spanning_tree(H, weight="km")
        tour = list(nx.dfs_preorder_nodes(T))
        ring = sum(nx.shortest_path_length(H, a, b, weight="lat_ms") for a, b in zip(tour, tour[1:] + tour[:1]))
        diam = max(nx.single_source_dijkstra_path_length(H, s_, weight="lat_ms")[t_] for s_ in H for t_ in H)
        km = sum(d["km"] for _, _, d in H.edges(data=True))
        it_mw = sum(w[i] for i in ids)
        g = C["gb300_nvl72"]
        racks = it_mw * 1000 / (g["rack_kw"] * (1 + C["non_rack_it_overhead"]))
        peak = racks * g["fp8_dense_ef_per_rack"] * 1e18
        frac = 0.90 * np.array([sum(perm[idx[i], m] * w[i] for i in ids) / it_mw for m in range(12)])
        eff = peak * C["mfu"]
        step_flop = 6 * params * C["tokens_per_step"]
        t_step = step_flop / (eff * float(frac.mean()) / 0.90)
        ov = {}
        for Hs in C["diloco_inner_steps"]:
            bytes_sync = params * (2.0 if Hs == 1 else C["pseudo_gradient_bytes_per_param"])
            t_comm = 2 * (len(ids) - 1) / len(ids) * bytes_sync / bw_bytes + ring / 1000 * 2
            ov[Hs] = t_comm / (Hs * t_step)
        monthly = eff * frac * HOURS * 3600 / (1 + ov[100])
        def months_to(start):
            cum = 0.0
            for k in range(120):
                mi = (start - 1 + k) % 12
                if cum + monthly[mi] >= target:
                    return k + (target - cum) / monthly[mi]
                cum += monthly[mi]
            return float("inf")
        res[name] = dict(nodes=ids, n_sites=len(ids), it_mw=it_mw, racks=racks, gpus=racks * g["gpus_per_rack"], peak_fp8_ef=peak / 1e18,
                         fibre_km=km, ring_latency_ms=ring, max_latency_ms=diam, params=params, overhead_by_H=ov,
                         months_to_target_june=months_to(6), annual_flop=monthly.sum(),
                         models_per_year=monthly.sum() / target)
    return dict(target_flop=target, params=params, clusters=res)


# ----------------------------------------------------------------------------- main
def era5_diagnostics(A, nodes):
    """Checks of the scenario inputs against ERA5 2010-2025: precipitation seasonality by supply regime, rain days by
    climate zone versus the fallback climatology, wet-day-threshold sensitivity, and node air temperature/humidity."""
    if ERA5_DIR is None:
        return None
    out = dict(regimes={}, zones={}, nodes={})
    for reg in sorted({n["regime"] for n in nodes}):
        P = []
        for n in [x for x in nodes if x["regime"] == reg]:
            dl = era5_daily_local(ERA5_DIR, f"{n['id']:02d} {n['name']}")
            if not dl:
                continue
            ys = sorted({d.year for d in dl})
            mm = np.zeros(12)
            for d, v in dl.items():
                mm[d.month - 1] += v
            P.append(mm / len(ys))
        P = np.mean(P, axis=0)
        prof = np.array(A["ice_permission_profiles"][reg], dtype=float)
        out["regimes"][reg] = dict(n_nodes=sum(1 for x in nodes if x["regime"] == reg), monthly_precip_mm=P.tolist(),
                                   annual_mm=float(P.sum()), dec_apr_share=float(P[[0, 1, 2, 3, 11]].sum() / P.sum()),
                                   driest_month=int(np.argmin(P)) + 1, permission_profile=prof.tolist(),
                                   permission_min_month=int(np.argmin(prof)) + 1,
                                   corr_precip_vs_permission=float(np.corrcoef(P, prof)[0, 1]),
                                   corr_precip_lag1_vs_permission=float(np.corrcoef(np.roll(P, 1), prof)[0, 1]))
    S = A["drying"]["sun_drying"]
    for z in sorted({n["zone"] for n in nodes}):
        zn = [n for n in nodes if n["zone"] == z]
        rd = np.mean([n["rain_days"] for n in zn], axis=0)
        win1 = np.mean([n["sun_window"] for n in zn], axis=0)
        w2 = []
        for n in zn:
            dl = era5_daily_local(ERA5_DIR, f"{n['id']:02d} {n['name']}")
            w2.append(rain_stats_from_daily(dl, S["days_needed"], S["wet_mm_sensitivity"])["window"])
        out["zones"][z] = dict(n_nodes=len(zn), era5_rain_days=rd.tolist(), fallback_rain_days=A["rain_days_default"][z],
                               era5_rain_days_annual=float(rd.sum()), fallback_rain_days_annual=float(sum(A["rain_days_default"][z])),
                               window_wet1mm=win1.tolist(), window_wet2mm=np.mean(w2, axis=0).tolist())
    for n in nodes:
        out["nodes"][n["id"]] = dict(t_air_c=n.get("era5_t_air_c"), rh_pct=n.get("era5_rh_pct"))
    ts = [n["era5_t_air_c"] for n in nodes if n.get("era5_t_air_c") is not None]
    rh = [n["era5_rh_pct"] for n in nodes if n.get("era5_rh_pct") is not None]
    out["t_air_range_c"] = [min(ts), max(ts)]; out["rh_range_pct"] = [min(rh), max(rh)]
    Q = A["aquaculture"]
    out["ras_ambient"] = {str(n["id"]): dict(era5_air_c=n["era5_t_air_c"], fallback_c=Q["node_ambient_water_c"].get(str(n["id"])))
                          for n in nodes if n["aqua"] and n.get("era5_t_air_c") is not None}
    return out


# ----------------------------------------------------------------------------- cold chain, self-cooling, barter, apiculture
def cold_chain(A, nodes, run):
    """Seafood cold chain. Heat-driven adsorption chillers (45-55 C drive, chilled water ~12-15 C) serve pre-cooling and
    processing-room cooling from rejected heat; chilling to 0 C and freezing to -25 C stay electric (vapour compression)."""
    K = A["cold_chain"]; aq = run["aq"]; Sx = A["aquaculture"].get("snapper_ras", {})
    out = dict(nodes={}, heat_mwh=0.0, cooling_heat_driven_mwh=0.0, elec_saved_mwh=0.0, elec_freeze_mwh=0.0, product_t=0.0)
    for i, n in enumerate(nodes):
        v = aq.get(n["id"])
        if not v:
            continue
        prod = v["t"] + v.get("snapper_t", 0.0) * Sx.get("fillet_yield_for_cold_chain", 1.0)
        c_hd = prod * 1000 * (K["precool_kwh_per_kg"] + K["process_room_kwh_per_kg"]) / 1000.0  # MWh cooling, heat-drivable
        heat_need = c_hd / K["adsorption_cop"]
        avail = float(run["heat_rejected"][i].sum())
        heat = min(heat_need, avail); served = heat * K["adsorption_cop"]
        saved = served / K["electric_chiller_cop"] - served * K["adsorption_aux_kwh_per_kwh"]
        freeze = prod * 1000 * (K["chill_kwh_per_kg"] / K["chill_cop"] + K["freeze_kwh_per_kg"] / K["freeze_cop"]) / 1000.0
        out["nodes"][n["id"]] = dict(product_t=prod, heat_mwh=heat, cooling_mwh=served)
        out["heat_mwh"] += heat; out["cooling_heat_driven_mwh"] += served; out["elec_saved_mwh"] += saved
        out["elec_freeze_mwh"] += freeze; out["product_t"] += prod
    tot = run["totals"]
    out["reuse_gain_pct_points"] = 100 * out["heat_mwh"] / 1000 / tot["heat_gwh"]
    out["freeze_heat_needed_if_ammonia_absorption_mwh"] = out["product_t"] * 1000 * (K["chill_kwh_per_kg"] + K["freeze_kwh_per_kg"]) / K["ammonia_absorption_cop"] / 1000
    return out


def self_cooling(A, nodes, run, cop=None):
    """Scenario: adsorption chillers driven by rejected heat cool the air-side residual (1 - recoverable fraction of IT heat)
    in hours when ERA5 air temperature exceeds the dry-cooler free-cooling limit, replacing electric chillers."""
    K = dict(A["cold_chain"]); N = A["network"]
    if cop is not None:
        K["adsorption_cop"] = cop
    if ERA5_DIR is None:
        return None
    peak_kw = 0.0
    served_m = np.zeros(12); heat_m = np.zeros(12); saved = 0.0; demand = 0.0
    for i, n in enumerate(nodes):
        h = era5_hourly(ERA5_DIR, f"{n['id']:02d} {n['name']}")
        if h is None:
            continue
        loc = h["time"] - np.timedelta64(6, "h"); mo = loc.astype("datetime64[M]").astype(int) % 12
        hot = h["temperature_2m"] > K["free_cooling_limit_c"]
        frac = np.array([hot[mo == m].mean() for m in range(12)])
        need = run["it_mwh"][i] * (1 - N["recoverable_heat_fraction_of_it"]) * frac  # MWh cooling
        heat_av = run["heat_rejected"][i]
        srv = np.minimum(need, heat_av * K["adsorption_cop"])
        peak_kw += n["it_mw"] * 1000 * (1 - N["recoverable_heat_fraction_of_it"])
        served_m += srv; heat_m += srv / K["adsorption_cop"]; demand += need.sum()
        saved += srv.sum() / K["self_cooling_baseline_cop"] - srv.sum() * K["adsorption_aux_kwh_per_kwh"]
    tot = run["totals"]
    external = run["ras_heat"].sum() + run["dry_heat"].sum()  # heat exported to processes outside the data centre
    internal = heat_m.sum()  # heat used to cool the data centre itself: not reuse under ERF (The Green Grid)
    E = A["economics"]
    capex = peak_kw * K["adsorption_capex_usd_per_kw_cooling"]
    saving_usd = saved * 1000 * E["electricity_usd_per_kwh"]
    return dict(cop=K["adsorption_cop"], chiller_capacity_mw=peak_kw / 1000, capex_usd=capex, saving_usd=saving_usd,
                simple_payback_years=capex / saving_usd if saving_usd > 0 else float("inf"),
                annualised_capex_usd=capex * crf(E["commercial_conservative"]["wacc"], K["adsorption_life_years"]),
                cooling_demand_gwh=demand / 1000, cooling_served_gwh=served_m.sum() / 1000, heat_gwh=heat_m.sum() / 1000,
                elec_saved_gwh=saved / 1000, reuse_pct=100 * external / 1000 / tot["heat_gwh"],
                erf_pct=100 * external / 1000 / (tot["facility_gwh"] - saved / 1000),
                internal_cooling_heat_gwh=internal / 1000, internal_cooling_share_of_heat_pct=100 * internal / 1000 / tot["heat_gwh"],
                pue=(tot["facility_gwh"] - saved / 1000) / tot["it_gwh"], monthly_heat_gwh=(heat_m / 1000).tolist())


def ras_effluent(A, run):
    """Fish-farm effluent and salt discharge; heat needed to concentrate snapper brine and recover its salt."""
    Q = A["aquaculture"]; Sx = Q["snapper_ras"]; aq = run["aq"]; D = A["drying"]
    cam_m3 = sum(v["volume_m3"] * Q["makeup_fraction_per_day"] * 365 for v in aq.values())
    snp_m3 = sum(v["snapper_volume_m3"] * Sx["makeup_fraction_per_day"] * 365 for v in aq.values())
    cam_salt = cam_m3 * Q["camaron_salt_kg_per_m3"] / 1000; snp_salt = snp_m3 * Sx["salt_kg_per_m3"] / 1000
    evap_t = snp_m3 * (1 - Sx["salt_kg_per_m3"] / 1000)  # approx. t water to evaporate
    heat = evap_t * drying_kwh_per_kg(A)  # MWh, open-dryer efficiency
    return dict(camaron_effluent_m3=cam_m3, camaron_salinity_g_l=Q["camaron_salt_kg_per_m3"], camaron_salt_t=cam_salt,
                snapper_effluent_m3=snp_m3, snapper_salinity_g_l=Sx["salt_kg_per_m3"], snapper_salt_t=snp_salt,
                brine_concentration_heat_gwh=heat / 1000, brine_share_of_rejected_pct=100 * heat / 1000 / run["totals"]["rejected_heat_gwh"])


def barter(A, run):
    """Drying service paid in kind (dried product at market value) versus cash. Costa Rican VAT applies to non-monetary
    consideration at normal market value (Decree 41779-H, arts. 13.3 and 17.3), so barter does not reduce tax."""
    T = A["tax"]
    feeds = [k for k, p in run["products"].items() if not p.get("retail", False) and k not in ("cafe", "harinas")]
    fee = sum(run["products"][k]["water_open_t"] * run["products"][k]["fee_usd_per_t_water"] + run["products"][k]["water_hp_t"] * run["products"][k]["fee_hp_usd_per_t_water"] for k in feeds)
    val = sum(run["products"][k]["dried_t"] * 1000 * A["drying"]["products"][k]["price_bulk_usd_kg"] for k in feeds)
    in_kind_t = sum(run["products"][k]["dried_t"] for k in feeds) * (fee / val if val else 0.0)
    cash = dict(vat_service=T["vat_general"] * fee, vat_goods=0.0)
    bart = dict(vat_service=T["vat_general"] * fee, vat_goods=T["vat_agri_inputs"] * fee)
    # net VAT between two VAT-registered businesses with full credit is zero in both cash and barter; a grower in the
    # special agricultural regime who cannot credit input VAT bears the service VAT in either case.
    net_registered = dict(cash=0.0, barter=0.0)
    return dict(service_value_usd=fee, dried_value_usd=val, in_kind_share=fee / val if val else 0.0, in_kind_t=in_kind_t,
                net_vat_registered=net_registered, vat_borne_if_no_credit_usd=T["vat_general"] * fee,
                cash=cash, barter=bart, extra_vat_barter_usd=bart["vat_goods"],
                income_tax_base_identical=True)


def aquafeed(A, run, loop):
    """Feed demand of camaron and snapper and the part met by local meals: cross-species by-product meals and banana meal."""
    Q = A["aquaculture"]; Sx = Q.get("snapper_ras", {})
    cam = sum(v["t"] for v in run["aq"].values()); snp = sum(v.get("snapper_t", 0.0) for v in run["aq"].values())
    fc = cam * Q["fcr_camaron"]; fs = snp * Q["snapper_fcr"]
    bm_av = run["products"]["harina_banano"]["dried_t"]
    bm_c = min(fc * Q["banana_meal_max_inclusion_camaron"], bm_av); bm_s = min(fs * Q["banana_meal_max_inclusion_snapper"], bm_av - bm_c)
    by_meal = loop["camaron_meal_to_snapper_protein_t"] / Q["camaron_meal_protein"] + loop["snapper_meal_to_camaron_protein_t"] / Q["snapper_meal_protein"]
    local = bm_c + bm_s + by_meal
    return dict(feed_camaron_t=fc, feed_snapper_t=fs, banana_meal_camaron_t=bm_c, banana_meal_snapper_t=bm_s,
                banana_meal_share_to_aquafeed=(bm_c + bm_s) / bm_av if bm_av else 0.0, byproduct_meal_t=by_meal,
                local_share_pct=100 * local / (fc + fs) if (fc + fs) else 0.0)


def apiculture(A, nodes, run, land_parts):
    """Rooftop nectar meadows (drone-sown each year, no pesticides) and apiaries at every node."""
    B = A["apiculture"]
    roof_ha = (land_parts["computing"] + land_parts["drying"] + land_parts["aquaculture"]) * B["roof_usable_fraction"]
    hives = B["hives_per_node"] * len(nodes)
    honey_t = hives * B["honey_kg_per_hive"] / 1000
    meadow_t = roof_ha * B["meadow_honey_kg_per_ha"] / 1000
    irr = None
    if ERA5_DIR is not None:
        tot_it = sum(n["it_mw"] for n in nodes); m3 = np.zeros(12)
        for n in nodes:
            h = era5_hourly(ERA5_DIR, f"{n['id']:02d} {n['name']}")
            if h is None or "et0_fao_evapotranspiration" not in h:
                continue
            loc = h["time"] - np.timedelta64(6, "h"); mo = loc.astype("datetime64[M]").astype(int) % 12
            yrs = len(set((loc.astype("datetime64[Y]").astype(int) + 1970).tolist()))
            et0 = np.array([np.nansum(h["et0_fao_evapotranspiration"][mo == m]) for m in range(12)]) / yrs
            pr = np.array([np.nansum(h["precipitation"][mo == m]) for m in range(12)]) / yrs
            deficit = np.maximum(B["crop_coefficient"] * et0 - B["effective_rain_fraction"] * pr, 0.0)  # mm/month
            m3 += deficit * 10.0 * roof_ha * n["it_mw"] / tot_it  # mm * 10 m3/ha
        irr = dict(monthly_m3=m3.tolist(), annual_m3=float(m3.sum()), dry_season_m3=float(m3[[0, 1, 2, 3, 11]].sum()))
    shelter = None
    if ERA5_DIR is not None:
        K = A["cold_chain"]; cool = 0.0
        for n in nodes:
            h = era5_hourly(ERA5_DIR, f"{n['id']:02d} {n['name']}")
            if h is None:
                continue
            yrs = len(set((h["time"].astype("datetime64[Y]").astype(int) + 1970).tolist()))
            hot_h = float((h["temperature_2m"] > B["hive_cooling_threshold_c"]).sum()) / yrs
            cool += B["hives_per_node"] * B["hive_shelter_cooling_w"] * hot_h / 1e6  # MWh
        brood = hives * B["brood_break_w_per_hive"] * B["brood_break_days"] * 24 / 1e6 / B["brood_break_cop"]
        shelter = dict(cooling_mwh=cool, heat_mwh=cool / K["adsorption_cop"], brood_break_elec_mwh=brood,
                       reuse_gain_pct_points=100 * cool / K["adsorption_cop"] / 1000 / run["totals"]["heat_gwh"])
    W = run["distilled_water"]
    return dict(roof_ha=roof_ha, hives=hives, shelter=shelter, honey_t=honey_t, meadow_honey_t=meadow_t,
                share_of_imports_pct=100 * honey_t / B["national_imports_t"], share_of_production_pct=100 * honey_t / B["national_production_t"],
                hives_share_pct=100 * hives / B["national_hives"],
                honey_value_usd=honey_t * 1000 * B["honey_price_usd_kg"],
                roof_capex_usd=roof_ha * 10000 * B["green_roof_capex_usd_per_m2"],
                seeding_usd_per_year=roof_ha * B["drone_seeding_usd_per_ha"],
                jobs_fte=hives / 100 * B["fte_per_100_hives"], irrigation=irr,
                condensate_available_m3=W["irrigation_process_m3"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--era5", type=Path, default=None, help="Folder produced by descargar_era5_costa_rica.py")
    ap.add_argument("--out", type=Path, default=HERE / "outputs")
    ap.add_argument("--synthetic", action="store_true", help="Run without ERA5 (regional climatologies and synthetic wind/solar); not the archived results")
    args = ap.parse_args(argv)
    if args.era5 is None and not args.synthetic:
        ap.error("--era5 FOLDER is required to reproduce the archived results (use --synthetic for the fallback mode)")
    if args.era5 is not None and not args.era5.is_dir():
        ap.error(f"ERA5 folder not found: {args.era5}")
    global ERA5_DIR
    ERA5_DIR = args.era5
    A, sites, edges = load_inputs()
    nodes, G = build_network(A, sites, edges, args.era5)
    args.out.mkdir(parents=True, exist_ok=True)
    runs = {c: run_network(A, nodes, perm_case=c, capacity_case=True) for c in ("normal", "dry_year", "firm", "seasonal")}
    nodes200, _ = build_network(A, sites, edges, args.era5, scale_it=200.0 / sum(n["it_mw"] for n in nodes))
    run200 = run_network(A, nodes200, perm_case="normal")
    comp = compare_systems(A, nodes, G, runs["normal"], runs["firm"], runs["dry_year"], run200, runs["seasonal"])
    farmer = farmer_economics(A, nodes)
    cam_total = sum(v["t"] for v in runs["normal"]["aq"].values())
    snap_total = sum(v.get("snapper_t", 0.0) for v in runs["normal"]["aq"].values())
    loops = {k: circular_loop(A, cam_total, k) for k in A["aquaculture"]["snapper_cases_t"]}
    if snap_total > 0:
        loops["nodes_ras"] = circular_loop(A, cam_total, snap_total)
    perm_by_case = {c: permission_matrix(A, nodes, c) for c in ("normal", "dry_year", "firm", "seasonal")}
    train = training(A, nodes, G, perm_by_case)
    sens_base, sens = sensitivity(A, nodes)
    econ = {pc: economics(A, nodes, comp, train["fibre_capex_usd"][1], price_case=pc) for pc in ("low", "central", "high")}
    econ_capex = {cc: economics(A, nodes, comp, train["fibre_capex_usd"][1], capex_case=cc) for cc in ("low", "high")}
    # link physical runs to funding: the community seafood is produced only where the community benefit is funded
    gift_by_case = {}
    for c in ("normal", "dry_year", "firm", "seasonal"):
        funded = not econ["central"][f"secadores_{c}"]["community_suspended"]
        gift_by_case[c] = funded
        if not funded:
            runs[c] = run_network(A, nodes, perm_case=c, capacity_case=True, gift=False)
    comp = compare_systems(A, nodes, G, runs["normal"], runs["firm"], runs["dry_year"], run200, runs["seasonal"])
    # commercial-conservative case as a physical run: unsold GPU-hours are powered down; no community seafood
    Kc = A["economics"]["commercial_conservative"]
    run_cons = run_network(A, nodes, perm_case="normal", util_mult=Kc["sold_fraction"], gift=False)
    comm = community(A, nodes, econ["central"])
    econ_cons = economics_conservative(A, econ["central"])
    K = A["economics"]["commercial_conservative"]; Cm = A["community"]
    for case in ("secadores_normal", "secadores_seasonal", "secadores_firm"):
        cc = comm["cases"][case]; ev = comm["households"] * Cm["ev_price_usd"]["central"]
        cb = econ_cons[case]["community_funded_usd"]
        cc["conservative_budget_usd"] = cb; cc["conservative_target_usd"] = econ_cons[case]["community_10pct_usd"]
        cc["conservative_suspended"] = cb <= 0.0
        gift = cc.get("seafood_cost_usd", 0.0)
        cb_ev = cb - min(gift, max(cb, 0.0))
        cc["conservative_seafood_funded"] = gift > 0 and cb >= gift
        cc["conservative_free_ev_years_ramp"] = ev_timeline(cb_ev, K["ramp"], ev, cc["charging_usd"])
        cc["central_free_ev_years_ramp"] = ev_timeline(cc["ev_budget_usd"], K["ramp"], ev, cc["charging_usd"])
        cc["central_free_ev_years_ramp_no_seafood"] = ev_timeline(cc["budget_usd"], K["ramp"], ev, cc["charging_usd"])
        cc["target_free_ev_years_ramp"] = ev_timeline(cc["target_usd"] - gift, K["ramp"], ev, cc["charging_usd"])
        cc["conservative_half_price_years_ramp"] = ev_timeline(cb_ev, K["ramp"], ev / 2, cc["charging_usd"])
    def _cut(Ax):
        cx = compare_systems(Ax, nodes, G, runs["normal"], runs["firm"], runs["dry_year"], run200, runs["seasonal"])
        return dict(cut_seasonal_vs_quantum_pct=100 * (1 - cx["secadores_seasonal"]["cue_g_per_kwh_it"]["marg_normal"] / cx["quantum_limon"]["cue_g_per_kwh_it"]["marg_normal"]),
                    cut_normal_vs_quantum_pct=100 * (1 - cx["secadores_normal"]["cue_g_per_kwh_it"]["marg_normal"] / cx["quantum_limon"]["cue_g_per_kwh_it"]["marg_normal"]),
                    cue_seasonal=cx["secadores_seasonal"]["cue_g_per_kwh_it"]["marg_normal"], cue_quantum=cx["quantum_limon"]["cue_g_per_kwh_it"]["marg_normal"])
    carbon_sens = carbon_sensitivity(A, _cut)
    S_ = A["drying"]["sun_drying"]
    persistence = {}
    for rr in sorted({0.0, S_["rain_persistence_r"], *S_["rain_persistence_range"]}):
        fe = farmer_economics(A, nodes, r=rr)
        persistence[str(rr)] = dict(banana_rainy_max=max(float(x["sun_feasibility"]) for x in fe if x["product"] == "banano" and 5 <= x["month"] <= 11),
                                    mango_oct=[float(x["sun_feasibility"]) for x in fe if x["product"] == "mango" and x["zone"] == "PN" and x["month"] == 10][0],
                                    mango_mar=[float(x["sun_feasibility"]) for x in fe if x["product"] == "mango" and x["zone"] == "PN" and x["month"] == 3][0])
    scale = {}
    for tot in (122.0, 200.0, 400.0):
        As = copy.deepcopy(A); As["network"]["sizing"]["total_it_mw"] = tot
        ns, Gs = build_network(As, sites, edges, args.era5)
        rs = run_network(As, ns, perm_case="normal")
        cs = {"secadores_normal": dict(it_mw=tot, it_gwh=rs["totals"]["it_gwh"], facility_gwh=rs["totals"]["facility_gwh"], grid_gwh=rs["totals"]["facility_gwh"])}
        es = economics(As, ns, cs, train["fibre_capex_usd"][1])["secadores_normal"]
        hh = comm["households"]
        scale[str(int(tot))] = dict(reuse_pct=rs["totals"]["reused_pct_of_heat"], erf_pct=rs["totals"]["erf_pct"], ebitda_usd=es["ebitda_usd"],
                                     community_usd=es["community_10pct_usd"], per_household_usd=es["community_10pct_usd"] / hh,
                                     rejected_gwh=rs["totals"]["rejected_heat_gwh"])
    clus = clusters(A, nodes, G, perm_by_case["normal"])
    clus_seasonal = clusters(A, nodes, G, perm_by_case["seasonal"])
    F = grid_factors(A)
    base = runs["normal"]
    key = dict(
        n_nodes=len(nodes), it_mw_total=float(sum(n["it_mw"] for n in nodes)),
        nodes_by_scale={s: sum(1 for n in nodes if n["scale"] == s) for s in ("hub", "medium", "small")},
        hydro_mw_total=float(sum(n["hydro_mw"] for n in nodes)),
        rain_day_source=sorted({n["rain_source"] for n in nodes}),
        era5=era5_diagnostics(A, nodes),
        totals={c: r["totals"] for c, r in runs.items()},
        website_capacity_case=runs["normal"]["capacity"],
        drying_kwh_per_kg_water=base["kwh_per_kg"],
        products={k: {kk: vv for kk, vv in v.items() if not isinstance(vv, list)} for k, v in base["products"].items()},
        aquaculture=dict(nodes=len(base["aq"]), camaron_t=cam_total, snapper_t=snap_total,
                         heat_camaron_gwh=sum(v["heat_camaron_mwh"] for v in base["aq"].values()) / 1000,
                         heat_snapper_gwh=sum(v["heat_snapper_mwh"] for v in base["aq"].values()) / 1000,
                         makeup_m3=sum(v["makeup_m3"] for v in base["aq"].values()), salt_t=sum(v["salt_t"] for v in base["aq"].values()),
                         snapper_makeup_m3=sum(v["snapper_volume_m3"] * A["aquaculture"].get("snapper_ras", {}).get("makeup_fraction_per_day", 0) * 365 for v in base["aq"].values()),
                         heat_gwh=sum(v["heat_mwh"] for v in base["aq"].values()) / 1000,
                         elec_gwh=sum(v["elec_mwh"] for v in base["aq"].values()) / 1000,
                         heat_kwh_per_kg_range=[min(v["heat_kwh_per_kg"] for v in base["aq"].values()), max(v["heat_kwh_per_kg"] for v in base["aq"].values())]),
        circular_loop=loops,
        comparison=comp,
        training=train,
        grid_factors_kg_per_kwh={k: v.tolist() for k, v in F.items()},
        sensitivity_base_margin_usd=sens_base, sensitivity=sens,
        distilled_water={c: r["distilled_water"] for c, r in runs.items()},
        economics=econ, economics_capex=econ_capex, scale_cases=scale, economics_conservative=econ_cons,
        cold_chain=cold_chain(A, nodes, base), self_cooling=self_cooling(A, nodes, base),
        self_cooling_cop_high=self_cooling(A, nodes, base, cop=A["cold_chain"]["adsorption_cop_range"][1]),
        self_cooling_cop_low=self_cooling(A, nodes, base, cop=A["cold_chain"]["adsorption_cop_range"][0]),
        barter=barter(A, base), ras_effluent=ras_effluent(A, base),
        gift_by_case=gift_by_case,
        conservative_physical=dict(totals=run_cons["totals"], aq_heat_gwh=run_cons["ras_heat"].sum() / 1000,
                                   camaron_t=sum(v["t"] for v in run_cons["aq"].values()), snapper_t=sum(v.get("snapper_t", 0.0) for v in run_cons["aq"].values())),
        aquaculture_accounts=aquaculture_accounts(A, base["aq"]),
        integrated={c: integrated_balance(A, nodes, runs[c], c, comm["cases"].get(f"secadores_{c}", dict(suspended=not gift_by_case[c])))
                    for c in ("normal", "dry_year", "firm", "seasonal")},
        integrated_conservative=integrated_balance(A, nodes, run_cons, "normal", dict(suspended=True)),
        optics_synchronous=dict({g: dict(extra_capex_usd=v["extra_optics_capex_usd"],
                                          annual_charge_usd=v["extra_optics_capex_usd"] * crf(A["economics"]["commercial_conservative"]["wacc"], A["economics"]["facility_life_years"]),
                                          headroom_after_usd=econ["central"]["secadores_normal"]["headroom_after_community_usd"] - v["extra_optics_capex_usd"] * crf(A["economics"]["commercial_conservative"]["wacc"], A["economics"]["facility_life_years"]))
                                 for g, v in training_scale_across(A, nodes, G, perm_by_case)["systems"].items()}),
        seafood_gift=seafood_gift_cost(A) if A["aquaculture"].get("community_seafood", {}).get("enabled") else None,
        training_scale_across=training_scale_across(A, nodes, G, perm_by_case),
        aquafeed=aquafeed(A, base, loops.get("nodes_ras", loops[A["aquaculture"]["central_loop_case"]])),
        apiculture=apiculture(A, nodes, base, comp["secadores_normal"]["land_parts_ha"]),
        carbon_sensitivity=carbon_sens, sun_persistence=persistence, community=comm, clusters=clus, clusters_seasonal=clus_seasonal,
        node_it_mw={n["id"]: n["it_mw"] for n in nodes},
        dryer_modes=base["modes"],
        dryer_designs=dryer_designs(A, nodes),
        heat_pump_sensitivity=smer_sensitivity(A, nodes),
        products_by_case={c: {k: {kk: vv for kk, vv in v.items() if not isinstance(vv, list)} for k, v in r["products"].items()} for c, r in runs.items()},
        monthly_by_product={k: v["monthly_processed_t"] for k, v in base["products"].items()},
        monthly_heat={c: dict(heat=r["heat_mwh"].sum(axis=0).tolist(), ras=r["ras_heat"].sum(axis=0).tolist(),
                              dry=r["dry_heat"].sum(axis=0).tolist(), rejected=r["heat_rejected"].sum(axis=0).tolist(),
                              dry_elec=r["dry_elec"].sum(axis=0).tolist()) for c, r in runs.items()},
    )
    (args.out / "results.json").write_text(json.dumps(key, indent=1, default=float), encoding="utf-8")
    with (args.out / "nodes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "operator", "region", "hydro_mw", "scale", "it_mw", "regime", "zone", "rain_source",
                    "it_gwh_normal", "heat_gwh", "drying_heat_gwh", "ras_heat_gwh", "rejected_heat_gwh",
                    "mango_fresh_t", "banano_fresh_t", "platano_fresh_t", "camaron_t", "products"])
        for i, n in enumerate(nodes):
            w.writerow([n["id"], n["name"], n["operator"], n["region"], n["hydro_mw"], n["scale"], n["it_mw"], n["regime"], n["zone"], n["rain_source"],
                        round(base["it_mwh"][i].sum() / 1000, 3), round(base["heat_mwh"][i].sum() / 1000, 3),
                        round(base["dry_heat"][i].sum() / 1000, 3), round(base["ras_heat"][i].sum() / 1000, 3),
                        round(base["heat_rejected"][i].sum() / 1000, 3),
                        round(base["products"]["mango"]["per_node_fresh_t"][i], 1), round(base["products"]["banano"]["per_node_fresh_t"][i], 1),
                        round(base["products"]["platano"]["per_node_fresh_t"][i], 1), base["aq"].get(n["id"], {}).get("t", 0),
                        ";".join(k for k, v in base["products"].items() if v["per_node_fresh_t"][i] > 0.5)])
    with (args.out / "monthly_network.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case", "month", "it_gwh", "facility_gwh", "heat_gwh", "drying_heat_gwh", "ras_heat_gwh", "rejected_heat_gwh",
                    "mango_t", "banano_t", "platano_t"])
        for c, r in runs.items():
            for mi in range(12):
                w.writerow([c, mi + 1, round(r["it_mwh"][:, mi].sum() / 1000, 3), round(r["fac_mwh"][:, mi].sum() / 1000, 3),
                            round(r["heat_mwh"][:, mi].sum() / 1000, 3), round(r["dry_heat"][:, mi].sum() / 1000, 3),
                            round(r["ras_heat"][:, mi].sum() / 1000, 3), round(r["heat_rejected"][:, mi].sum() / 1000, 3),
                            round(r["products"]["mango"]["monthly_processed_t"][mi], 1),
                            round(r["products"]["banano"]["monthly_processed_t"][mi], 1),
                            round(r["products"]["platano"]["monthly_processed_t"][mi], 1)])
    with (args.out / "farmer_drying_economics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(farmer[0])); w.writeheader(); w.writerows(farmer)
    with (args.out / "fibre_edges.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["from", "to", "route_km", "one_way_latency_ms"])
        for a, b, d in G.edges(data=True):
            w.writerow([a, b, round(d["km"], 2), round(d["lat_ms"], 4)])
    print(json.dumps(dict(it_mw=key["it_mw_total"], totals=key["totals"]["normal"],
                          dried_t={k: round(v["dried_t"], 1) for k, v in key["products"].items()}), indent=1, default=float))
    return key


if __name__ == "__main__":
    main()
