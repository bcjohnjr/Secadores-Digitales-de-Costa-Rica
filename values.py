"""Formatted result values for the manuscript text (Spanish and English number formats)."""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fmt(x, d=0, lang="es"):
    s = f"{x:,.{d}f}"
    if lang == "es":
        s = s.replace(",", " " if abs(x) >= 10000 else "").replace(".", ",")
    return s


def values(lang):
    R = json.loads((HERE / "outputs" / "results.json").read_text(encoding="utf-8"))
    F = list(csv.DictReader((HERE / "outputs" / "farmer_drying_economics.csv").open(encoding="utf-8")))
    f = lambda x, d=0: fmt(x, d, lang)
    import math as _m
    yrs = lambda x: (("suspendido" if lang == "es" else "suspended") if not _m.isfinite(x) else fmt(x, 1, lang))
    T = R["totals"]; P = R["products"]; C = R["comparison"]; TR = R["training"]; S = TR["systems"]; L = R["circular_loop"]
    V = {}
    V["it_mw"] = f(R["it_mw_total"]); V["hydro_mw"] = f(R["hydro_mw_total"], 1)
    V["it_share_hydro"] = f(100 * R["it_mw_total"] / R["hydro_mw_total"], 1)
    for c in ("normal", "dry_year", "firm", "seasonal"):
        V[f"it_{c}"] = f(T[c]["it_gwh"], 1); V[f"fac_{c}"] = f(T[c]["facility_gwh"], 1); V[f"heat_{c}"] = f(T[c]["heat_gwh"], 1)
        V[f"cf_{c}"] = f(100 * T[c]["it_capacity_factor"], 0); V[f"rej_{c}"] = f(T[c]["rejected_heat_gwh"], 1)
    V["ras_heat"] = f(T["normal"]["ras_heat_gwh"], 1); V["dry_heat"] = f(T["normal"]["drying_heat_gwh"], 1)
    reused = T["normal"]["ras_heat_gwh"] + T["normal"]["drying_heat_gwh"]
    V["reused"] = f(reused, 1); V["reused_pct_heat"] = f(100 * reused / T["normal"]["heat_gwh"], 1)
    for k in ("normal", "seasonal", "dry_year", "firm"):
        V[f"erf_{k}"] = f(100 * C[f"secadores_{k}"]["erf"], 1)
    V["cap_heat"] = f(R["website_capacity_case"]["heat_mwh"] / 1000, 1); V["cap_water"] = f(R["website_capacity_case"]["water_removed_t"], 0)
    V["kwh_kg"] = f(R["drying_kwh_per_kg_water"], 2)
    for k in P:
        p = P[k]
        V[f"{k}_fresh"] = f(p["fresh_processed_t"]); V[f"{k}_dried"] = f(p["dried_t"]); V[f"{k}_water"] = f(p["water_removed_t"])
        V[f"{k}_heat"] = f(p["heat_mwh"] / 1000, 1); V[f"{k}_rev"] = f(p["revenue_usd"] / 1e6, 2); V[f"{k}_margin"] = f(p["gross_margin_usd"] / 1e6, 2)
        V[f"{k}_yield"] = f(100 * p["dried_yield"], 1); V[f"{k}_wpk"] = f(p["water_per_kg_fresh"], 3)
        V[f"{k}_avail"] = f(p["fresh_available_t"]); V[f"{k}_un"] = f(p["unprocessed_t"]); V[f"{k}_hp"] = f(p["water_hp_t"])
        V[f"{k}_be"] = f(p["breakeven_price_usd_kg"], 2) if p["breakeven_price_usd_kg"] else "–"
        V[f"{k}_heat0"] = f(p["heat_mwh"] / 1000, 0)
    dried = sum(p["dried_t"] for p in P.values()); rev = sum(p["revenue_usd"] for p in P.values()); mar = sum(p["gross_margin_usd"] for p in P.values())
    V["dried_total"] = f(dried); V["rev_total"] = f(rev / 1e6, 1); V["margin_total"] = f(mar / 1e6, 1)
    V["fee_t_water"] = f(P["mango"]["fee_usd_per_t_water"], 1); V["fee_feed"] = f(P["heno_pasto"]["fee_usd_per_t_water"], 1)
    def fr(prod, zone, month, key):
        r = [x for x in F if x["product"] == prod and x["zone"] == zone and int(x["month"]) == month][0]
        return float(r[key])
    V["mango_sd_t"] = f(fr("mango", "PN", 3, "secadores_net_usd_t")); V["mango_lpg_t"] = f(fr("mango", "PN", 3, "lpg_net_usd_t"))
    V["mango_sun_mar"] = f(fr("mango", "PN", 3, "sun_net_usd_t")); V["mango_sun_oct"] = f(fr("mango", "PN", 10, "sun_net_usd_t"))
    V["mango_feas_mar"] = f(fr("mango", "PN", 3, "sun_feasibility"), 2); V["mango_feas_oct"] = f(fr("mango", "PN", 10, "sun_feasibility"), 2)
    V["banano_sd_t"] = f(fr("banano", "CA", 7, "secadores_net_usd_t")); V["banano_lpg_t"] = f(fr("banano", "CA", 7, "lpg_net_usd_t"))
    V["platano_sd_t"] = f(fr("platano", "ZN", 7, "secadores_net_usd_t")); V["platano_lpg_t"] = f(fr("platano", "ZN", 7, "lpg_net_usd_t"))
    gaps = [fr(p_, z_, 7, "secadores_net_usd_t") - fr(p_, z_, 7, "lpg_net_usd_t") for p_, z_ in (("mango", "PN"), ("banano", "CA"), ("platano", "ZN"))]
    V["lpg_gap_lo"] = f(min(gaps)); V["lpg_gap_hi"] = f(max(gaps))
    V["lpg_fuel_t_water"] = f(fr("mango", "PN", 3, "lpg_fuel_usd_t_fresh") / P["mango"]["water_per_kg_fresh"], 0)
    rainy = [float(x["sun_feasibility"]) for x in F if x["product"] == "banano" and 5 <= int(x["month"]) <= 11]
    V["banana_rainy_feas_max"] = f(100 * max(rainy), 0)
    A = R["aquaculture"]
    V["cam_t"] = f(A["camaron_t"]); V["cam_heat"] = f(A["heat_gwh"], 1); V["cam_elec"] = f(A["elec_gwh"], 1)
    V["cam_kwh_lo"] = f(A["heat_kwh_per_kg_range"][0], 1); V["cam_kwh_hi"] = f(A["heat_kwh_per_kg_range"][1], 1)
    V["ras_water"] = f(C["secadores_normal"]["ras_makeup_water_m3"])
    for k, v in L.items():
        k = k.replace(".", "p")
        V[f"loop_{k}_snap"] = f(v["snapper_fishmeal_protein_replaced_pct"], 1); V[f"loop_{k}_cam"] = f(v["camaron_fishmeal_protein_replaced_pct"], 1)
        V[f"loop_{k}_surplus"] = f(v["snapper_meal_surplus_protein_t"], 0); V[f"loop_{k}_fm"] = f(v["fishmeal_avoided_t"], 0)
        V[f"loop_{k}_heat"] = f(v["meal_drying_heat_mwh"] / 1000, 2); V[f"loop_{k}_snapmeal"] = f(v["snapper_meal_t"], 0)
        V[f"loop_{k}_cammeal"] = f(v["camaron_meal_t"], 0)
    for k, v in C.items():
        for acc, x in v["cue_g_per_kwh_it"].items():
            V[f"cue_{k}_{acc}"] = f(x, 1)
        for acc, x in v["carbon_t"].items():
            V[f"co2_{k}_{acc}"] = f(x / 1000, 1)
        V[f"land_{k}"] = f(v["land_ha"], 1); V[f"landmw_{k}"] = f(v["land_ha"] / v["it_mw"], 2)
        V[f"facgwh_{k}"] = f(v["facility_gwh"], 0); V[f"itgwh_{k}"] = f(v["it_gwh"], 0); V[f"grid_{k}"] = f(v["grid_gwh"], 1)
    nat = C["quantum_limon"]["facility_gwh"] / 0.146
    V["nat_gwh"] = f(nat, 0)
    for k, x in C.items():
        V[f"share_{k}"] = f(100 * x["facility_gwh"] / nat, 1); V[f"gridshare_{k}"] = f(100 * x["grid_gwh"] / nat, 1)
        V[f"drydraw_{k}"] = f(x["dry_season_grid_gwh"], 0)
    qmax = max(R["node_it_mw"].values()) * 1.1e6; V["dt_hub_mw"] = f(qmax / 1e6, 0)
    V["dt_hub_20"] = f(qmax / (1000 * 4186 * 20), 2); V["dt_hub_5"] = f(qmax / (1000 * 4186 * 5), 2); V["dt_pilot_5"] = f(4.4e6 / (1000 * 4186 * 5), 2)
    V["ere_normal"] = f(C["secadores_normal"]["ere"], 2)
    V["q_water_mm3"] = f(C["quantum_limon"]["cooling_water_m3"] / 1e6, 2); V["q_wue"] = f(C["quantum_limon"]["wue_l_per_kwh_it"], 1)
    V["pn_hourly"] = f(100 * C["palo_negro_38mw"]["own_renewable_hourly_share"], 1); V["pn_ratio"] = f(100 * C["palo_negro_38mw"]["own_generation_to_load_ratio"], 1)
    V["pn_curt"] = f(C["palo_negro_38mw"]["own_curtailed_or_export_gwh"], 1); V["pn120_hourly"] = f(100 * C["palo_negro_120mw"]["own_renewable_hourly_share"], 1)
    jobs = C["secadores_normal"]["jobs_fte"]; V["jobs_total"] = f(sum(jobs.values())); V["jobs_dc"] = f(jobs["data_centre"]); V["jobs_dry"] = f(jobs["drying"]); V["jobs_aq"] = f(jobs["aquaculture"])
    V["lpg_credit"] = f(C["secadores_normal"]["lpg_drying_co2_avoided_if_counterfactual_t"] / 1000, 1)
    V["fruit_water"] = f(C["secadores_normal"]["fruit_water_evaporated_t"])
    V["cut_seasonal_vs_q"] = f(100 * (1 - C["secadores_seasonal"]["cue_g_per_kwh_it"]["marg_normal"] / C["quantum_limon"]["cue_g_per_kwh_it"]["marg_normal"]), 0)
    V["cut_normal_vs_q"] = f(100 * (1 - C["secadores_normal"]["cue_g_per_kwh_it"]["marg_normal"] / C["quantum_limon"]["cue_g_per_kwh_it"]["marg_normal"]), 0)
    V["fibre_km"] = f(TR["fibre_route_km"], 0); V["fibre_edges"] = f(TR["fibre_edges"])
    V["fibre_lo"] = f(TR["fibre_capex_usd"][0] / 1e6, 1); V["fibre_mid"] = f(TR["fibre_capex_usd"][1] / 1e6, 1); V["fibre_hi"] = f(TR["fibre_capex_usd"][2] / 1e6, 1)
    V["lat_max"] = f(TR["max_one_way_latency_ms"], 2); V["lat_ring"] = f(TR["ring_latency_ms"], 1); V["bw"] = f(TR["inter_site_bandwidth_tbps"], 1)
    for key, v in S.items():
        k = key.replace("|", "_")
        V[f"tr_{k}_m6"] = f(v["months_to_target_start_june"], 1); V[f"tr_{k}_m1"] = f(v["months_to_target_start_jan"], 1)
        V[f"tr_{k}_racks"] = f(v["racks"]); V[f"tr_{k}_gpus"] = f(v["gpus"]); V[f"tr_{k}_ef"] = f(v["peak_fp8_ef"], 0)
        V[f"tr_{k}_annual"] = f(v["annual_training_flop"] / 1e27, 2)
        for h, o in v["overhead_by_H"].items():
            V[f"tr_{k}_ov{h}"] = f(100 * o, 2 if 100 * o < 1 else 1)
    V["sens_base"] = f(R["sensitivity_base_margin_usd"] / 1e6, 1)
    for s in R["sensitivity"]:
        key = {"Dryer capital and O&M ±50%": "dryer", "Feedstock availability ×0.5 / ×2": "avail", "Bulk vs premium dried price": "premium",
               "Processing cost ±30%": "proc", "Feedstock price ±30%": "feed", "Bulk dried price ±30%": "price",
               "Heat-pump dryer capital ±50%": "hpcap", "Heat-pump SMER 2–4 kg/kWh": "smer"}[s["label"]]
        V[f"sens_{key}_lo"] = f(s["low"] / 1e6, 1); V[f"sens_{key}_hi"] = f(s["high"] / 1e6, 1)
    # thermal efficiency and dryer designs
    Tn = T["normal"]
    V["reuse_pct"] = f(Tn["reused_pct_of_heat"], 1); V["erf_pct_n"] = f(Tn["erf_pct"], 1)
    V["water_evap"] = f(Tn["water_evaporated_t"]); V["drying_elec"] = f(Tn["drying_elec_gwh"], 1); V["dry_eff"] = f(Tn["drying_energy_efficiency_pct"], 1)
    for c in ("dry_year", "seasonal", "firm"):
        V[f"reuse_pct_{c}"] = f(T[c]["reused_pct_of_heat"], 1)
    for d, v in R["dryer_designs"].items():
        V[f"des_{d}_reuse"] = f(v["reused_pct_of_heat"], 1); V[f"des_{d}_erf"] = f(v["erf_pct"], 1)
        V[f"des_{d}_elec"] = f(v["drying_elec_gwh"], 1); V[f"des_{d}_eff"] = f(v["drying_energy_efficiency_pct"], 0)
        V[f"des_{d}_kgkwh"] = f(v["kg_water_per_kwh_input"], 2); V[f"des_{d}_water"] = f(v["water_evaporated_t"])
        V[f"des_{d}_margin"] = f(v["margin_usd"] / 1e6, 1); V[f"des_{d}_tot"] = f((v["margin_usd"] + v["water_value_usd"]) / 1e6, 1)
        V[f"des_{d}_un"] = f(v["unprocessed_t"]); V[f"des_{d}_cond"] = f(v["condensate_m3"]); V[f"des_{d}_heat"] = f(v["reused_heat_gwh"], 0)
        V[f"des_{d}_dried"] = f(v["dried_t"]); V[f"des_{d}_kgelec"] = f(v["kg_water_per_kwh_elec"], 1)
    V["des_hp_all_loss"] = f(-(R["dryer_designs"]["hp_all"]["margin_usd"] + R["dryer_designs"]["hp_all"]["water_value_usd"]) / 1e6, 1)
    M = R["dryer_modes"]
    V["kg_open"] = f(1 / (M["open"]["heat"] + M["open"]["elec"]), 2); V["kg_hp"] = f(1 / (M["hp"]["heat"] + M["hp"]["elec"]), 2)
    V["hp_ratio"] = f((M["open"]["heat"] + M["open"]["elec"]) / (M["hp"]["heat"] + M["hp"]["elec"]), 1)
    V["kgelec_open"] = f(1 / M["open"]["elec"], 1); V["kgelec_hp"] = f(1 / M["hp"]["elec"], 1)
    V["hp_heat_kg"] = f(M["hp"]["heat"], 2); V["hp_elec_kg"] = f(M["hp"]["elec"], 2); V["open_elec_kg"] = f(M["open"]["elec"], 2)
    W = R["distilled_water"]["normal"]
    V["dw_cond"] = f(W["condensate_m3"]); V["dw_retail"] = f(W["retail_m3"]); V["dw_rev"] = f(W["retail_revenue_usd"] / 1e6, 2)
    V["dw_net"] = f((W["retail_revenue_usd"] - W["retail_treatment_cost_usd"]) / 1e6, 2)
    V["dw_ras_need"] = f(W["ras_need_m3"])
    Wf = R["dryer_designs"]["food_hp"]; V["dw_food_cond"] = f(Wf["condensate_m3"])
    for x in R["heat_pump_sensitivity"]["retail_cap"]:
        V[f"cap_{int(x['cap_m3'])}_net"] = f(x["net_usd"] / 1e6, 2)
    sm = {x["smer"]: x for x in R["heat_pump_sensitivity"]["smer"]}
    V["fruit_dried"] = f(sum(P[k]["dried_t"] for k in ("mango", "pina", "banano", "platano")))
    V["feed_dried"] = f(sum(P[k]["dried_t"] for k in ("harina_banano", "rastrojo_pina", "pulpa_cafe", "heno_pasto", "harinas")))
    V["feed_un"] = f(sum(P[k]["unprocessed_t"] for k in P))
    V["fruit_margin"] = f(sum(P[k]["gross_margin_usd"] for k in ("mango", "pina", "banano", "platano")) / 1e6, 1)
    V["feed_margin"] = f(sum(P[k]["gross_margin_usd"] for k in ("harina_banano", "rastrojo_pina", "pulpa_cafe", "heno_pasto")) / 1e6, 1)
    V["cafe_service"] = f(P["cafe"]["revenue_usd"] / 1e6, 2); V["cafe_fee_t"] = f(P["cafe"]["revenue_usd"] / P["cafe"]["fresh_processed_t"], 1)
    V["cafe_green_t"] = f(1591979 * 46 / 1000)
    cs = C["secadores_normal"]
    V["lpg_gross"] = f(cs["lpg_drying_co2_avoided_if_counterfactual_t"] / 1000, 1)
    V["lpg_net_n"] = f(cs["lpg_drying_co2_avoided_net_t"]["marg_normal"] / 1000, 1)
    V["dry_elec_co2"] = f(cs["drying_elec_co2_t"]["marg_normal"] / 1000, 1)
    V["total_value"] = f((sum(p["gross_margin_usd"] for p in P.values()) + W["retail_revenue_usd"] - W["retail_treatment_cost_usd"] + W["ras_value_usd"] + W["other_value_usd"]) / 1e6, 1)
    # compute economics (central GPU-hour price) and community package
    EC = R["economics"]["central"]
    for k, e in EC.items():
        V[f"ec_{k}_rev"] = f(e["revenue_usd"] / 1e9, 2); V[f"ec_{k}_ebitda"] = f(e["ebitda_usd"] / 1e9, 2)
        V[f"ec_{k}_capex"] = f(e["capex_usd"] / 1e9, 1); V[f"ec_{k}_refresh"] = f(e["refresh_reserve_usd"] / 1e9, 2)
        V[f"ec_{k}_cash"] = f(e["cash_after_refresh_usd"] / 1e9, 2); V[f"ec_{k}_comm"] = f(e["community_funded_usd"] / 1e6, 0); V[f"ec_{k}_target"] = f(e["community_10pct_usd"] / 1e6, 0)
        V[f"ec_{k}_margin"] = f(100 * e["ebitda_margin"], 0); V[f"ec_{k}_payback"] = f(e["payback_years"], 1)
        V[f"ec_{k}_gpus"] = f(e["gpus"]); V[f"ec_{k}_util"] = f(100 * e["utilisation_of_gpu_hours"], 0)
        V[f"ec_{k}_ebitdamw"] = f(e["ebitda_per_mw_usd"] / 1e6, 1)
    for pc in ("low", "high"):
        V[f"ec_net_ebitda_{pc}"] = f(R["economics"][pc]["secadores_normal"]["ebitda_usd"] / 1e9, 2)
        V[f"ec_net_payback_capex_{pc}"] = f(R["economics_capex"][pc]["secadores_normal"]["payback_years"], 1)
    CM = R["community"]
    V["cm_pop"] = f(CM["population"]); V["cm_hh"] = f(CM["households"]); V["cm_districts"] = f(CM["districts"])
    V["cm_charging_gwh"] = f(CM["charging_gwh"], 0); V["cm_kwh_ev"] = f(CM["ev_kwh_per_year"], 0)
    for c, v in CM["cases"].items():
        k = c.replace("secadores_", "")
        V[f"cm_{k}_budget"] = f(v["budget_usd"] / 1e6, 0); V[f"cm_{k}_perhh"] = f(v["budget_per_household_usd"], 0)
        V[f"cm_{k}_charging"] = f(v["charging_usd"] / 1e6, 1); V[f"cm_{k}_steady"] = f(100 * v["steady_state_share_of_budget"], 0) if v["budget_usd"] > 0 else "–"
        for o, x in v["options"].items():
            V[f"cm_{k}_{o.replace('|', '_')}_yrs"] = yrs(x["years_with_charging"])
            V[f"cm_{k}_{o.replace('|', '_')}_cost"] = f(x["cost_usd"] / 1e9, 2)
    for k, v in CM["comparators"].items():
        V[f"cm_{k}_pop"] = f(v["population"]); V[f"cm_{k}_perhh"] = f(v["per_household_usd"], 0); V[f"cm_{k}_budget"] = f(v["hypothetical_budget_usd"] / 1e6, 0)
    V["cm_palo_negro_bagaces_perhh38"] = f(CM["comparators"]["palo_negro_bagaces"]["per_household_38mw_usd"], 0)
    CL = R["clusters"]; V["cl_params"] = f(CL["params"] / 1e12, 1)
    for k, v in CL["clusters"].items():
        V[f"cl_{k}_n"] = f(v["n_sites"]); V[f"cl_{k}_mw"] = f(v["it_mw"], 0); V[f"cl_{k}_gpus"] = f(v["gpus"])
        V[f"cl_{k}_km"] = f(v["fibre_km"], 0); V[f"cl_{k}_ring"] = f(v["ring_latency_ms"], 2); V[f"cl_{k}_months"] = f(v["months_to_target_june"], 1)
        V[f"cl_{k}_models"] = f(v["models_per_year"], 1); V[f"cl_{k}_ov10"] = f(100 * v["overhead_by_H"]["10"], 1); V[f"cl_{k}_ov1"] = f(100 * v["overhead_by_H"]["1"], 0)
        V[f"cl_{k}_seasonal_models"] = f(R["clusters_seasonal"]["clusters"][k]["models_per_year"], 1)
    V["net_annual_e27"] = f(S["secadores_net_normal|gb300_nvl72"]["annual_training_flop"] / 1e27, 1)
    V["net_share_nat"] = f(100 * C["secadores_normal"]["facility_gwh"] / nat, 1)
    V["it_share_hydro0"] = f(100 * R["it_mw_total"] / R["hydro_mw_total"], 0)
    V["fac_share_hydro"] = f(100 * R["it_mw_total"] * 1.1 / R["hydro_mw_total"], 0)
    for k, x in R["scale_cases"].items():
        V[f"sc{k}_reuse"] = f(x["reuse_pct"], 0); V[f"sc{k}_comm"] = f(x["community_usd"] / 1e6, 0); V[f"sc{k}_perhh"] = f(x["per_household_usd"], 0)
    V["balsa_mw"] = f(R["node_it_mw"]["12"], 1)
    nm = R["node_it_mw"]; V["node_max_mw"] = f(max(nm.values()), 0); V["node_min_mw"] = f(min(nm.values()), 1)
    # referee-driven additions: carbon sensitivity, sun-drying persistence, commercial risk, land/water boundaries, mass flows
    CS = R["carbon_sensitivity"]
    V["cut_flat"] = f(CS["flat"]["cut_seasonal_vs_quantum_pct"], 0); V["cue_flat_seasonal"] = f(CS["flat"]["cue_seasonal"], 1)
    V["cut_scale_lo"] = f(CS["scale_0.5"]["cut_seasonal_vs_quantum_pct"], 0); V["cut_scale_hi"] = f(CS["scale_1.5"]["cut_seasonal_vs_quantum_pct"], 0)
    V["cue_q_lo"] = f(CS["scale_0.5"]["cue_quantum"], 0); V["cue_q_hi"] = f(CS["scale_1.5"]["cue_quantum"], 0)
    SP = R["sun_persistence"]
    for k, x in SP.items():
        kk = k.replace(".", "p")
        V[f"sp{kk}_banana"] = f(100 * x["banana_rainy_max"], 0); V[f"sp{kk}_mango_oct"] = f(x["mango_oct"], 2); V[f"sp{kk}_mango_mar"] = f(x["mango_mar"], 2)
    for k, e in R["economics"]["central"].items():
        V[f"ec_{k}_capchg"] = f(e["capital_charge_wacc_usd"] / 1e9, 2); V[f"ec_{k}_net"] = f(e["ebitda_less_capital_charge_usd"] / 1e9, 2)
    for k, e in R["economics_conservative"].items():
        V[f"cons_{k}_ebitda"] = f(e["ebitda_usd"] / 1e9, 2); V[f"cons_{k}_comm"] = f(e["community_10pct_usd"] / 1e6, 0)
        V[f"cons_{k}_free"] = f(e["free_cash_after_capital_tax_community_usd"] / 1e9, 2)
    V["cons_price_factor"] = f(100 * R["economics_conservative"]["secadores_normal"]["price_factor"], 0)
    for c, v in R["community"]["cases"].items():
        k = c.replace("secadores_", "")
        V[f"cm_{k}_cons_budget"] = f(v["conservative_budget_usd"] / 1e6, 0)
        V[f"cm_{k}_cons_ev_ramp"] = yrs(v["conservative_free_ev_years_ramp"]); V[f"cm_{k}_central_ev_ramp"] = yrs(v["central_free_ev_years_ramp"])
        V[f"cm_{k}_cons_half_ramp"] = yrs(v["conservative_half_price_years_ramp"]); V[f"cm_{k}_target_ev_ramp"] = yrs(v["target_free_ev_years_ramp"])
        V[f"cm_{k}_ev_ramp_nofish"] = yrs(v.get("central_free_ev_years_ramp_no_seafood", v["central_free_ev_years_ramp"]))
    for k, x in C.items():
        if "land_direct_ha" in x:
            V[f"landd_{k}"] = f(x["land_direct_ha"], 1); V[f"landg_{k}"] = f(x["land_new_generation_ha"], 0)
    for k, p_ in P.items():
        V[f"{k}_removed"] = f(p_["pretreatment_removed_t"])
        V[f"{k}_haul"] = f(p_["haul_usd"] / 1e6, 2)
    V["haul_total"] = f(sum(p_["haul_usd"] for p_ in P.values()) / 1e6, 1)
    V["removed_total"] = f(sum(p_["pretreatment_removed_t"] for p_ in P.values()))
    V["fresh_total"] = f(sum(p_["fresh_processed_t"] for p_ in P.values()))
    # ERA5 2010-2025: wind calibration, PV, hydro seasonality, sun windows, node climate
    E = R.get("era5")
    pn = C["palo_negro_38mw"]
    if "wind_calibration" in pn:
        W = pn["wind_calibration"]
        V["w_k"] = f(W["k"], 2); V["w_raw"] = f(100 * W["raw_era5_cf"], 1); V["w_pool"] = f(100 * W["pooled_observed_cf"], 1)
        V["w_o24"] = f(100 * W["per_year"]["2024"]["observed_cf"], 1); V["w_m24"] = f(100 * W["per_year"]["2024"]["modelled_cf"], 1)
        V["w_o25"] = f(100 * W["per_year"]["2025"]["observed_cf"], 1); V["w_m25"] = f(100 * W["per_year"]["2025"]["modelled_cf"], 1)
        V["w_cf"] = f(100 * pn["wind_cf"], 1); V["w_cf_lo"] = f(100 * pn["wind_cf_range"][0], 1); V["w_cf_hi"] = f(100 * pn["wind_cf_range"][1], 1)
        V["pv_cf"] = f(100 * pn["pv_cf"], 1); V["pv_cf_lo"] = f(100 * pn["pv_cf_range"][0], 1); V["pv_cf_hi"] = f(100 * pn["pv_cf_range"][1], 1)
        mw = pn["monthly_wind_cf"]
        V["w_cf_jan"] = f(100 * mw[0], 0); V["w_cf_sep"] = f(100 * mw[8], 0); V["w_cf_oct"] = f(100 * mw[9], 0)
        V["pn_lo"] = f(100 * pn["renewable_share_range"][0], 0); V["pn_hi"] = f(100 * pn["renewable_share_range"][1], 0)
        p1 = C["palo_negro_120mw"]
        V["pn120_lo"] = f(100 * p1["renewable_share_range"][0], 0); V["pn120_hi"] = f(100 * p1["renewable_share_range"][1], 0)
    if E:
        rg = E["regimes"]
        cs = [x["corr_precip_vs_permission"] for x in rg.values()]
        V["e_corr_lo"] = f(min(cs), 2); V["e_corr_hi"] = f(max(cs), 2)
        ds = [x["dec_apr_share"] for x in rg.values()]
        V["e_dry_lo"] = f(100 * min(ds), 0); V["e_dry_hi"] = f(100 * max(ds), 0)
        V["e_dry_car"] = f(100 * rg["C_caribe_norte"]["dec_apr_share"], 0); V["e_dry_pac"] = f(100 * rg["P_pacifico"]["dec_apr_share"], 0)
        V["e_dry_are"] = f(100 * rg["R_embalse_arenal"]["dec_apr_share"], 0)
        an = [x["annual_mm"] for x in rg.values()]
        V["e_mm_lo"] = f(min(an), 0); V["e_mm_hi"] = f(max(an), 0)
        Z = E["zones"]
        V["e_rd_lo"] = f(min(z["era5_rain_days_annual"] for z in Z.values()), 0); V["e_rd_hi"] = f(max(z["era5_rain_days_annual"] for z in Z.values()), 0)
        V["e_rdf_lo"] = f(min(z["fallback_rain_days_annual"] for z in Z.values()), 0); V["e_rdf_hi"] = f(max(z["fallback_rain_days_annual"] for z in Z.values()), 0)
        V["e2_mango_mar"] = f(Z["PN"]["window_wet2mm"][2], 2); V["e2_mango_oct"] = f(Z["PN"]["window_wet2mm"][9], 2)
        V["e2_banana_max"] = f(100 * max(max(Z[z]["window_wet2mm"][4:11]) for z in ("CA", "ZN")), 0)
        V["e_t_lo"] = f(E["t_air_range_c"][0], 1); V["e_t_hi"] = f(E["t_air_range_c"][1], 1)
        V["e_rh_lo"] = f(E["rh_range_pct"][0], 0); V["e_rh_hi"] = f(E["rh_range_pct"][1], 0)
        ra = [x["era5_air_c"] for x in E["ras_ambient"].values()]
        V["ras_t_lo"] = f(min(ra), 1); V["ras_t_hi"] = f(max(ra), 1)
    # node-sized RAS and feedstock
    aqn = [n for n in R["node_it_mw"]]
    Aq = R["aquaculture"]
    V["cam_per_mw"] = f(100)
    V["ras_ls"] = f(C["secadores_normal"]["ras_makeup_water_m3"] / (365 * 86400) * 1000, 0)
    V["ras_vs_q"] = f(100 * C["secadores_normal"]["ras_makeup_water_m3"] / C["quantum_limon"]["cooling_water_m3"], 0)
    V["cam_nat_lo"] = f(Aq["camaron_t"] / 2500, 1); V["cam_nat_hi"] = f(Aq["camaron_t"] / 2200, 1)
    # seafood at all nodes, cold chain, self-cooling, barter, honey
    QA = json.loads((HERE / "assumptions.json").read_text(encoding="utf-8"))
    Qa = QA["aquaculture"]; Sx = Qa["snapper_ras"]
    V["snap_t"] = f(Aq["snapper_t"]); V["aq_t"] = f(Aq["camaron_t"] + Aq["snapper_t"]); V["aq_nodes"] = f(Aq["nodes"])
    V["aq_heat_cam"] = f(Aq["heat_camaron_gwh"], 1); V["aq_heat_snap"] = f(Aq["heat_snapper_gwh"], 1)
    V["aq_ls"] = f(Aq["makeup_m3"] / (365 * 86400) * 1000, 0); V["aq_makeup"] = f(Aq["makeup_m3"])
    V["aq_vs_q"] = f(100 * Aq["makeup_m3"] / C["quantum_limon"]["cooling_water_m3"], 0)
    V["salt_t"] = f(Aq["salt_t"]); V["salt_musd"] = f(Aq["salt_t"] * 1000 * Qa["salt_usd_per_kg"] / 1e6, 1)
    imp = 2086.0
    GS = R.get("seafood_gift") or dict(camaron_t=0.0, snapper_t=0.0, total_t=0.0, population=0.0, cost_usd=0.0, retail_value_usd=0.0, capex_usd=0.0, cost_per_person_usd=0.0)
    cam_m = Aq["camaron_t"] - GS["camaron_t"]; snp_m = Aq["snapper_t"] - GS["snapper_t"]
    V["cam_mkt_t"] = f(cam_m); V["snap_mkt_t"] = f(snp_m); V["aq_mkt_t"] = f(cam_m + snp_m)
    V["gift_t"] = f(GS["total_t"]); V["gift_cam_t"] = f(GS["camaron_t"]); V["gift_snp_t"] = f(GS["snapper_t"])
    V["gift_pop"] = f(GS["population"]); V["gift_kg"] = f(Qa.get("community_seafood", {}).get("kg_per_person_year", 0.0))
    V["gift_cost"] = f(GS["cost_usd"] / 1e6, 1); V["gift_value"] = f(GS["retail_value_usd"] / 1e6, 1); V["gift_pp"] = f(GS["cost_per_person_usd"])
    V["gift_capex"] = f(GS["capex_usd"] / 1e6, 0); V["aq_mult"] = f((Aq["camaron_t"] + Aq["snapper_t"]) / (Qa["national_camaron_t"] + Qa["national_snapper_t"]), 1)
    if GS["total_t"]:
        V["gift_kgc"] = f(sum(GS["cost_per_kg_camaron"].values()), 2); V["gift_kgs"] = f(sum(GS["cost_per_kg_snapper"].values()), 2)
        V["gift_share_budget"] = f(100 * GS["cost_usd"] / R["community"]["cases"]["secadores_normal"]["budget_usd"], 0)
    V["imp_sub_t"] = f(imp); V["exp_t"] = f(cam_m - imp)
    val = imp * 1000 * Qa["camaron_price_usd_kg"] + (cam_m - imp) * 1000 * Qa["camaron_price_export_usd_kg"] + snp_m * 1000 * Sx["price_usd_kg"]
    V["aq_value"] = f(val / 1e6, 0)
    AF = R["aquafeed"]
    V["feed_local_pct"] = f(AF["local_share_pct"], 0); V["bm_aq_t"] = f(AF["banana_meal_camaron_t"] + AF["banana_meal_snapper_t"])
    V["byp_meal_t"] = f(AF["byproduct_meal_t"]); V["feed_aq_t"] = f(AF["feed_camaron_t"] + AF["feed_snapper_t"])
    XS = R.get("training_scale_across")
    if XS:
        V["xs_pairs_base"] = f(XS["base_pairs"]); V["xs_grad_tb"] = f(XS["gradient_tb"], 0)
        for g, s_ in (("gb", "gb300_nvl72"), ("vr", "vera_rubin_nvl144")):
            x = XS["systems"][s_]
            V[f"xs_{g}_ov_off"] = f(100 * x["overhead_off_the_shelf_base"], 0); V[f"xs_{g}_ov_xgs"] = f(100 * x["overhead_xgs_base"], 0)
            V[f"xs_{g}_pairs"] = f(x["pairs_needed_xgs"]); V[f"xs_{g}_pairs_off"] = f(x["pairs_needed_off_the_shelf"])
            V[f"xs_{g}_capex"] = f(x["extra_optics_capex_usd"] / 1e6, 0); V[f"xs_{g}_step"] = f(x["step_time_s"], 2)
            for case in ("normal", "seasonal", "dry_year"):
                for mode in ("strict", "elastic"):
                    c = x["cases"][case][mode]
                    V[f"xs_{g}_{case}_{mode}_m6"] = f(c["months_to_target_start_june"], 2)
                    V[f"xs_{g}_{case}_{mode}_ann"] = f(c["annual_flop"] / 1e27, 1)
                    V[f"xs_{g}_{case}_{mode}_full"] = f(c["full_months"])
            n_ = x["cases"]["normal"]
            V[f"xs_{g}_strict_loss"] = f(100 * (1 - n_["strict"]["annual_flop"] / n_["elastic"]["annual_flop"]), 0)
    if R.get("self_cooling"):
        V["sc_int"] = f(R["self_cooling"]["internal_cooling_heat_gwh"], 0); V["sc_int_pct"] = f(R["self_cooling"]["internal_cooling_share_of_heat_pct"], 0)
    CP = R.get("conservative_physical")
    if CP:
        V["cons_reuse"] = f(CP["totals"]["reused_pct_of_heat"], 1); V["cons_dried"] = f(CP["totals"]["dried_t"]); V["cons_it"] = f(CP["totals"]["it_gwh"], 0)
    for c in ("seasonal", "dry_year"):
        V[f"{c}_dried"] = f(R["totals"][c]["dried_t"]); V[f"{c}_reuse"] = f(R["totals"][c]["reused_pct_of_heat"], 1)
    AA = R.get("aquaculture_accounts")
    if AA:
        V["aqa_sales"] = f(AA["sales_usd"] / 1e6, 1); V["aqa_cost"] = f(AA["cash_cost_usd"] / 1e6, 1); V["aqa_loss"] = f(-AA["margin_usd"] / 1e6, 1)
        V["gift_exp_loss"] = f(-AA["gift_if_exported_margin_usd"] / 1e6, 1); V["gift_exp_rev"] = f(AA["gift_if_exported_revenue_usd"] / 1e6, 1)
    IN = R.get("integrated")
    if IN:
        I = IN["normal"]
        V["int_gwh"] = f(I["integrated_gwh"], 0); V["int_pct"] = f(I["integrated_over_dc_pct"], 1); V["int_dry_e"] = f(I["drying_elec_gwh"], 0)
        V["int_ras_e"] = f(I["ras_elec_gwh"], 0); V["int_ev_e"] = f(I["ev_charging_gwh"], 0); V["int_fac"] = f(I["facility_gwh"], 0)
        V["int_co2"] = f(I["carbon_integrated_t"]["marg_normal"] / 1000, 0); V["dc_co2"] = f(I["carbon_dc_t"]["marg_normal"] / 1000, 0)
        V["ras_crit_mw"] = f(I["ras_critical_mw"], 0); V["ras_heat_mw"] = f(I["ras_mean_heat_mw"], 0); V["tank_h"] = f(I["tank_inertia_hours_per_k"], 0)
        V["ras_curt_gwh"] = f(I["ras_heat_in_curtailed_hours_gwh"], 1); V["bk_mw"] = f(I["backup_heat_pump_mw"], 1); V["bk_gwh"] = f(I["backup_heat_pump_elec_gwh"], 1)
        V["bk_cost"] = f(I["backup_cost_usd"] / 1e6, 1); V["bk_co2"] = f(I["backup_co2_t"]["marg_normal"] / 1000, 1)
        S_ = IN["seasonal"]; V["ras_curt_s"] = f(S_["ras_heat_in_curtailed_hours_gwh"], 1); V["bk_gwh_s"] = f(S_["backup_heat_pump_elec_gwh"], 1)
        V["int_s_pct"] = f(S_["integrated_over_dc_pct"], 1)
    en = R["economics"]["central"]["secadores_normal"]
    V["p_full"] = f(en["price_for_full_community_usd_h"], 3); V["p_zero"] = f(en["price_for_zero_margin_usd_h"], 2)
    V["p_full_pct"] = f(100 * (1 - en["price_for_full_community_usd_h"] / 5.10), 2)
    V["q_water_usd"] = f(R["economics"]["central"]["quantum_limon"]["water_upper_bound_usd"] / 1e6, 1)
    OP = R.get("optics_synchronous")
    if OP:
        V["opt_gb_ann"] = f(OP["gb300_nvl72"]["annual_charge_usd"] / 1e6, 1); V["opt_gb_def"] = f(-OP["gb300_nvl72"]["headroom_after_usd"] / 1e6, 1)
        V["opt_vr_ann"] = f(OP["vera_rubin_nvl144"]["annual_charge_usd"] / 1e6, 1)
    if XS:
        for g, s_ in (("gb", "gb300_nvl72"), ("vr", "vera_rubin_nvl144")):
            se = XS["systems"][s_]["sensitivity"]
            V[f"xs_{g}_pmin"] = f(se["pairs_min"]); V[f"xs_{g}_pmax"] = f(se["pairs_max"])
            V[f"xs_{g}_mmin"] = f(se["months_min"], 1); V[f"xs_{g}_mmax"] = f(se["months_max"], 1)
    V["dt_hub_it"] = f(max(R["node_it_mw"].values()), 0)
    CC = R["cold_chain"]
    V["cc_t"] = f(CC["product_t"]); V["cc_heat"] = f(CC["heat_mwh"], 0); V["cc_gain"] = f(CC["reuse_gain_pct_points"], 2)
    V["cc_saved"] = f(CC["elec_saved_mwh"], 0); V["cc_freeze"] = f(CC["elec_freeze_mwh"], 0); V["cc_nh3"] = f(CC["freeze_heat_needed_if_ammonia_absorption_mwh"] / 1000, 1)
    SC = R["self_cooling"]
    if SC:
        V["sc_heat"] = f(SC["heat_gwh"], 0); V["sc_reuse"] = f(SC["reuse_pct"], 1); V["sc_pue"] = f(SC["pue"], 3)
        V["sc_saved"] = f(SC["elec_saved_gwh"], 0); V["sc_served"] = f(SC["cooling_served_gwh"], 0); V["sc_demand"] = f(SC["cooling_demand_gwh"], 0)
        V["sc_erf"] = f(SC["erf_pct"], 1)
    BT = R["barter"]
    V["bt_share"] = f(100 * BT["in_kind_share"], 0); V["bt_vat"] = f(BT["barter"]["vat_service"] / 1e6, 1); V["bt_extra"] = f(BT["extra_vat_barter_usd"] / 1e6, 2)
    V["bt_service"] = f(BT["service_value_usd"] / 1e6, 1)
    AP = R["apiculture"]
    V["ap_roof"] = f(AP["roof_ha"], 0); V["ap_hives"] = f(AP["hives"]); V["ap_honey"] = f(AP["honey_t"], 0); V["ap_meadow"] = f(AP["meadow_honey_t"], 0)
    V["ap_imp"] = f(AP["share_of_imports_pct"], 0); V["ap_prod"] = f(AP["share_of_production_pct"], 0); V["ap_hivepct"] = f(AP["hives_share_pct"], 0)
    V["ap_value"] = f(AP["honey_value_usd"] / 1e6, 2); V["ap_capex"] = f(AP["roof_capex_usd"] / 1e6, 0); V["ap_seed"] = f(AP["seeding_usd_per_year"] / 1000, 0)
    V["ap_jobs"] = f(AP["jobs_fte"], 0)
    if AP.get("shelter"):
        V["ap_sh_cool"] = f(AP["shelter"]["cooling_mwh"], 0); V["ap_sh_heat"] = f(AP["shelter"]["heat_mwh"], 0); V["ap_brood"] = f(AP["shelter"]["brood_break_elec_mwh"], 0)
    if AP.get("irrigation"):
        V["ap_irr"] = f(AP["irrigation"]["annual_m3"])
    V["heno_un"] = f(P["heno_pasto"]["unprocessed_t"]); V["pulpa_un"] = f(P["pulpa_cafe"]["unprocessed_t"])
    V["heno_un_pct"] = f(100 * P["heno_pasto"]["unprocessed_t"] / P["heno_pasto"]["fresh_available_t"], 0)
    import csv as _csv
    nd = list(_csv.DictReader((HERE / "outputs" / "nodes.csv").open(encoding="utf-8")))
    def zr(z):
        x = [r for r in nd if r["zone"] == z]
        return 100 * sum(float(r["drying_heat_gwh"]) + float(r["ras_heat_gwh"]) for r in x) / sum(float(r["heat_gwh"]) for r in x)
    for z in ("CA", "PC", "PN", "VC", "ZN"):
        V[f"zr_{z}"] = f(zr(z), 0)
    # referee V6: funding rule, matched carbon, adsorption sensitivity, effluent
    EC = R["economics"]["central"]
    V["cm_share_headroom"] = f(100 * EC["secadores_normal"]["community_share_of_headroom"], 1)
    V["cm_headroom"] = f(EC["secadores_normal"]["headroom_after_community_usd"] / 1e6, 1)
    V["cm_firm_share_headroom"] = f(100 * EC["secadores_firm"]["community_share_of_headroom"], 0)
    V["cm_seasonal_target"] = f(EC["secadores_seasonal"]["community_10pct_usd"] / 1e6, 0)
    qs = C["quantum_limon_seasonal"]; sds = C["secadores_seasonal"]
    V["cue_qs"] = f(qs["cue_g_per_kwh_it"]["marg_normal"], 1)
    V["cut_matched"] = f(100 * (1 - sds["cue_g_per_kwh_it"]["marg_normal"] / qs["cue_g_per_kwh_it"]["marg_normal"]), 0)
    V["co2_qs"] = f(qs["carbon_t"]["marg_normal"] / 1000, 0); V["it_qs"] = f(qs["it_gwh"], 0)
    V["co2_sds"] = f(sds["carbon_t"]["marg_normal"] / 1000, 0); V["it_sds"] = f(sds["it_gwh"], 0)
    SCc = R["self_cooling"]; SCh = R["self_cooling_cop_high"]
    if SCc:
        V["sc_capex"] = f(SCc["capex_usd"] / 1e6, 0); V["sc_save_m"] = f(SCc["saving_usd"] / 1e6, 1); V["sc_pay"] = f(SCc["simple_payback_years"], 1)
        V["sc_ann"] = f(SCc["annualised_capex_usd"] / 1e6, 1); V["sc_mw"] = f(SCc["chiller_capacity_mw"], 0)
        V["sch_saved"] = f(SCh["elec_saved_gwh"], 0); V["sch_reuse"] = f(SCh["reuse_pct"], 1)
    RE = R["ras_effluent"]
    V["eff_cam"] = f(RE["camaron_effluent_m3"]); V["eff_snp"] = f(RE["snapper_effluent_m3"]); V["brine_heat"] = f(RE["brine_concentration_heat_gwh"], 0)
    V["brine_pct"] = f(RE["brine_share_of_rejected_pct"], 0); V["snp_salt"] = f(RE["snapper_salt_t"]); V["cam_salt"] = f(RE["camaron_salt_t"])
    V["cut_range"] = V["cut_flat"] if V["cut_flat"] == V["cut_matched"] else f"{V['cut_flat']}–{V['cut_matched']}"
    return V, R
