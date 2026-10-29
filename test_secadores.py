"""Consistency tests for secadores_model.py (python test_secadores.py)."""
import numpy as np
from pathlib import Path
import secadores_model as m

A, sites, edges = m.load_inputs()
nodes, G = m.build_network(A, sites, edges)

def test_network():
    assert len(nodes) == 32 and abs(sum(n["it_mw"] for n in nodes) - A["network"]["sizing"]["total_it_mw"]) < 0.1
    for n in nodes:
        assert n["it_mw"] * A["network"]["pue"] <= 0.25 * n["hydro_mw"] + 1e-6 or n["it_mw"] <= A["network"]["sizing"]["min_it_mw"] + 1e-9
    assert G.number_of_edges() == 33 and __import__("networkx").is_connected(G)

def test_heat_balance():
    for case in ("normal", "dry_year", "firm", "seasonal"):
        r = m.run_network(A, nodes, perm_case=case)
        lhs = r["ras_heat"] + r["dry_heat"] + r["heat_rejected"]
        assert np.allclose(lhs, r["heat_mwh"], rtol=1e-9, atol=1e-6)
        assert (r["heat_rejected"] >= -1e-6).all()
        assert (r["perm"] <= 1.0 + 1e-12).all() and (r["perm"] >= 0).all()

def test_mass_balance():
    for k, p in A["drying"]["products"].items():
        d, w = m.product_yields(p)
        assert abs(d + w - p["edible_fraction"]) < 1e-12
        solids_in = p["edible_fraction"] * (1 - p["moisture_fresh"])
        assert abs(d * (1 - p["moisture_dried"]) - solids_in) < 1e-12

def test_loop_caps():
    for case in A["aquaculture"]["snapper_cases_t"]:
        L = m.circular_loop(A, 1500.0, case)
        assert L["camaron_meal_to_snapper_protein_t"] <= L["camaron_meal_protein_t"] + 1e-9
        assert L["snapper_meal_to_camaron_protein_t"] <= L["snapper_meal_protein_t"] + 1e-9
        assert L["snapper_fishmeal_protein_replaced_pct"] <= 100 * A["aquaculture"]["max_fishmeal_protein_replacement_snapper_diet"] + 1e-9
        assert L["camaron_fishmeal_protein_replaced_pct"] <= 100 * A["aquaculture"]["max_fishmeal_protein_replacement_camaron_diet"] + 1e-9

def test_deterministic():
    a = m.run_network(A, nodes)["totals"]; b = m.run_network(A, nodes)["totals"]
    assert a == b

def test_heat_pump_and_water():
    for d in ("open", "hybrid", "heat_first", "food_hp", "hp_all"):
        r = m.run_network(A, nodes, dryer_mode=d)
        lhs = r["ras_heat"] + r["dry_heat"] + r["heat_rejected"]
        assert np.allclose(lhs, r["heat_mwh"], rtol=1e-9, atol=1e-6)
        W = r["distilled_water"]
        assert W["condensate_m3"] <= r["totals"]["water_hp_t"] + 1e-6
        assert W["retail_m3"] <= A["drying"]["distilled_water"]["retail_cap_m3_per_year"] + 1e-9
        assert W["retail_m3"] <= W["retail_eligible_m3"] + 1e-9
        assert abs(W["retail_m3"] + W["ras_makeup_m3"] + W["irrigation_process_m3"] - W["condensate_m3"]) < 1e-6
        for p in r["products"].values():
            assert p["fresh_processed_t"] <= p["fresh_available_t"] + 1e-6 and p["unprocessed_t"] >= -1e-6
        if d == "open":
            assert W["condensate_m3"] == 0.0

def test_economics_and_community():
    import json
    R = json.loads((m.HERE / "outputs" / "results.json").read_text())
    for k, e in R["economics"]["central"].items():
        assert abs(e["revenue_usd"] - e["opex_usd"] - e["ebitda_usd"]) < 1
        assert e["utilisation_of_gpu_hours"] <= 0.9 + 1e-9
        assert abs(e["community_10pct_usd"] - 0.1 * e["ebitda_usd"]) < 1
    C = R["community"]
    assert abs(sum(v["households"] for v in C["per_node"].values()) - C["households"]) < 1e-6
    for cl in R["clusters"]["clusters"].values():
        assert cl["overhead_by_H"]["100"] < cl["overhead_by_H"]["1"]

def test_era5_year_boundary_and_windows():
    rows = [{"time_utc": f"2010-01-01T{h:02d}:00", "precipitation": "0.0"} for h in range(24)]
    rows += [{"time_utc": f"2010-01-02T{h:02d}:00", "precipitation": "0.01"} for h in range(24)]
    rows += [{"time_utc": f"2010-01-03T{h:02d}:00", "precipitation": "0.0"} for h in range(24)]
    rows += [{"time_utc": f"2010-01-04T{h:02d}:00", "precipitation": "0.0"} for h in range(24)]
    daily = m.daily_from_rows(rows, years=(2010, 2010))
    assert min(daily).year == 2010  # the six UTC hours that fall on 31 Dec 2009 locally are excluded
    st = m.rain_stats_from_daily(daily, 3)
    assert st["years"] == 1
    # daily totals stay below 1 mm, so every complete 3-day window is dry
    assert st["window"][0] == 1.0
    assert abs(m.window_probability([0] * 12)[0] - 1.0) < 1e-12
    p = 1 - 15 / 31
    assert abs(m.window_probability([15] + [0] * 11, 3, 0.0)[0] - p ** 3) < 1e-12

def _synthetic_era5(years=(2024, 2025), v=7.0, ghi_peak=900.0):
    t = np.arange(np.datetime64(f"{years[0]}-01-01T00"), np.datetime64(f"{years[1] + 1}-01-01T00"), np.timedelta64(1, "h"))
    hr = (t - t.astype("datetime64[D]")).astype(int)
    loc = (hr - 6) % 24
    ghi = np.where((loc >= 6) & (loc <= 18), ghi_peak * np.sin(np.pi * (loc - 6) / 12), 0.0)
    rng = np.random.default_rng(1)
    return dict(time=t, wind_speed_100m=np.clip(v + rng.normal(0, 2.5, t.size), 0, None), shortwave_radiation=ghi,
                temperature_2m=np.full(t.size, 26.0), precipitation=np.zeros(t.size), relative_humidity_2m=np.full(t.size, 80.0))

def test_wind_calibration_and_palo_negro_balance():
    h = _synthetic_era5()
    cal = m.wind_calibration(A, h)
    W = A["comparators"]["palo_negro_bagaces"]["era5_wind"]
    m_ = (h["time"].astype("datetime64[Y]").astype(int) + 1970) >= 2024
    assert abs(m.wind_power_curve(cal["k"] * h["wind_speed_100m"][m_], W).mean() - cal["pooled_observed_cf"]) < 1e-6
    pv = m.pv_output_per_mw_ac(A, h)
    assert pv.min() >= 0 and pv.max() <= 1
    C = A["comparators"]["palo_negro_bagaces"]
    key = (str(Path("SYNTH")), C["era5_site"])
    m._ERA5_CACHE[key] = h
    old = m.ERA5_DIR; m.ERA5_DIR = Path("SYNTH")
    try:
        r = m.palo_negro_hourly(A, 38.0)
    finally:
        m.ERA5_DIR = old; m._ERA5_CACHE.pop(key, None)
    assert 0 < r["hourly_renewable_share"] <= 1
    # energy balance: renewable used + grid = load, per year
    for py in r["per_year"]:
        assert 0 <= py["renewable_share"] <= 1
    assert abs(r["renewable_used_mwh"] + r["grid_mwh"].sum() - r["load_mw"] * 8760) / (r["load_mw"] * 8760) < 0.01

def test_ras_scales_with_it():
    aq = m.aquaculture(A, nodes)
    Q = A["aquaculture"]
    assert len(aq) == 32
    cam = sum(v["t"] for v in aq.values()); snp = sum(v["snapper_t"] for v in aq.values())
    g = m.seafood_gift(A)
    assert abs(cam - Q["national_multiple"] * Q["national_camaron_t"] - g["camaron_t"]) < 1e-6
    assert abs(snp - Q["national_multiple"] * Q["national_snapper_t"] - g["snapper_t"]) < 1e-6
    tot = sum(n["it_mw"] for n in nodes)
    for n in nodes:
        assert abs(aq[n["id"]]["t"] / cam - n["it_mw"] / tot) < 1e-9

def test_cold_chain_barter_apiculture():
    r = m.run_network(A, nodes, perm_case="normal")
    cc = m.cold_chain(A, nodes, r)
    assert cc["heat_mwh"] <= r["heat_rejected"].sum() + 1e-6
    b = m.barter(A, r)
    assert b["barter"]["vat_service"] == b["cash"]["vat_service"] and b["barter"]["vat_goods"] >= 0
    lp = dict(computing=10.0, drying=20.0, aquaculture=5.0)
    ap = m.apiculture(A, nodes, r, lp)
    assert abs(ap["roof_ha"] - 35.0 * A["apiculture"]["roof_usable_fraction"]) < 1e-9
    assert abs(ap["honey_t"] - ap["hives"] * A["apiculture"]["honey_kg_per_hive"] / 1000) < 1e-9

def test_community_funding_rule():
    import math
    R = m.json.loads((m.HERE / "outputs" / "results.json").read_text(encoding="utf-8"))
    for k, e in R["economics"]["central"].items():
        assert e["community_funded_usd"] <= e["community_10pct_usd"] + 1e-6
        assert e["community_funded_usd"] <= max(0.0, e["ebitda_less_capital_charge_usd"]) + 1e-6
    for k, e in R["economics_conservative"].items():
        assert e["community_funded_usd"] <= max(0.0, e["distributable_usd"]) + 1e-6
    assert R["community"]["cases"]["secadores_seasonal"]["suspended"]

def test_seafood_gift():
    g = m.seafood_gift_cost(A)
    G = A["aquaculture"]["community_seafood"]
    assert abs(g["total_t"] - g["population"] * G["kg_per_person_year"] / 1000) < 1e-9
    assert abs(g["camaron_t"] + g["snapper_t"] - g["total_t"]) < 1e-9
    R = m.json.loads((m.HERE / "outputs" / "results.json").read_text(encoding="utf-8"))
    for k, c in R["community"]["cases"].items():
        assert c["seafood_paid_usd"] <= max(c["budget_usd"], 0.0) + 1e-6
        assert abs(c["ev_budget_usd"] - (c["budget_usd"] - c["seafood_paid_usd"])) < 1e-6

def test_scale_across_bounds():
    R = m.json.loads((m.HERE / "outputs" / "results.json").read_text(encoding="utf-8"))
    X = A["compute"]["scale_across"]
    for gen, s in R["training_scale_across"]["systems"].items():
        assert s["overhead_xgs_base"] <= s["overhead_off_the_shelf_base"]
        assert s["pairs_needed_xgs"] <= s["pairs_needed_off_the_shelf"]
        assert s["overhead_xgs_needed"] <= X["target_exposed_overhead"] + 1e-12
        for case, r in s["cases"].items():
            assert r["strict"]["annual_flop"] <= r["elastic"]["annual_flop"] * (1 + 1e-12)

def test_erf_external_boundary():
    # ERF counts only heat exported outside the data centre; heat used to cool the data centre itself is excluded
    R = m.json.loads((m.HERE / "outputs" / "results.json").read_text(encoding="utf-8"))
    sc = R["self_cooling"]; T = R["totals"]["normal"]
    if sc:
        assert abs(sc["reuse_pct"] - T["reused_pct_of_heat"]) < 1e-9
        assert abs(sc["erf_pct"] - 100 * T["reused_heat_gwh"] / (T["facility_gwh"] - sc["elec_saved_gwh"])) < 1e-9
        assert sc["internal_cooling_heat_gwh"] > 0

def test_scenarios_linked_to_funding():
    R = m.json.loads((m.HERE / "outputs" / "results.json").read_text(encoding="utf-8"))
    E = R["economics"]["central"]; Aq = A["aquaculture"]
    base = Aq["national_multiple"] * (Aq["national_camaron_t"] + Aq["national_snapper_t"])
    for c, g in R["gift_by_case"].items():
        assert g == (not E[f"secadores_{c}"]["community_suspended"])
    cp = R["conservative_physical"]
    assert abs(cp["camaron_t"] + cp["snapper_t"] - base) < 1e-6
    assert abs(cp["totals"]["it_gwh"] - R["totals"]["normal"]["it_gwh"] * A["economics"]["commercial_conservative"]["sold_fraction"]) < 1e-6
    I = R["integrated"]["normal"]
    assert abs(I["integrated_gwh"] - (I["facility_gwh"] + I["drying_elec_gwh"] + I["ras_elec_gwh"] + I["ev_charging_gwh"])) < 1e-9

def test_era5_required():
    try:
        m.main(["--out", "/tmp/_never"])
    except SystemExit as e:
        assert e.code != 0
    else:
        raise AssertionError("missing --era5 should fail")

if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f(); print("PASS", name)
