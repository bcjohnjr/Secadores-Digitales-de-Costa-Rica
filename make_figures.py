#!/usr/bin/env python3
"""Figures for the Secadores Digitales manuscript (Spanish and English labels).
Usage: python make_figures.py [--lang es|en|both]   (reads outputs/ written by secadores_model.py)"""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "savefig.dpi": 300, "axes.titlesize": 8.5, "axes.titleweight": "bold"})
C = dict(hub="#056f4a", medium="#249b59", small="#86bf3f", fibre="#0088cc", q="#b0413e", pn="#c98a2b",
         mango="#e8a33d", banano="#d9c63a", platano="#7a9a3a", ras="#2b7bb9", meal="#7b5ea7", rej="#c9c9c9",
         sun="#e07b39", sd="#1f7a5a", lpg="#8a8a8a", fresh="#5b8bd6")
MES = {"es": ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"], "en": ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]}
T = {
 "lon": {"es": "Longitud (°)", "en": "Longitude (°)"}, "lat": {"es": "Latitud (°)", "en": "Latitude (°)"},
 "hub": {"es": "Nodo grande (≥20 MW TI)", "en": "Hub node (≥20 MW IT)"}, "medium": {"es": "Nodo mediano (5–20 MW TI)", "en": "Medium node (5–20 MW IT)"},
 "small": {"es": "Nodo pequeño (<5 MW TI)", "en": "Small node (<5 MW IT)"}, "fibre": {"es": "Fibra oscura conceptual", "en": "Conceptual dark fibre"},
 "quantum": {"es": "Quantum (Limón), 200 MW", "en": "Quantum (Limón), 200 MW"}, "palo": {"es": "Palo Negro (Bagaces), 38 MW", "en": "Palo Negro (Bagaces), 38 MW"},
 "it_month": {"es": "Energía TI mensual (GWh)", "en": "Monthly IT energy (GWh)"},
 "normal": {"es": "Interrumpible, año normal", "en": "Interruptible, normal year"}, "dry_year": {"es": "Interrumpible, año seco", "en": "Interruptible, dry year"},
 "seasonal": {"es": "Guiado por la estación lluviosa", "en": "Rainy-season-led"}, "firm": {"es": "Suministro firme", "en": "Firm supply"},
 "marg": {"es": "Factor marginal (kg CO₂/kWh)", "en": "Marginal factor (kg CO₂/kWh)"},
 "marg_normal": {"es": "Año normal", "en": "Normal year"}, "marg_dry_year": {"es": "Año seco", "en": "Dry year"},
 "gwh_th": {"es": "Calor anual (GWhₜ)", "en": "Annual heat (GWhₜ)"},
 "mango": {"es": "Mango", "en": "Mango"}, "banano": {"es": "Banano", "en": "Banana"}, "platano": {"es": "Plátano", "en": "Plantain"},
 "ras": {"es": "RAS (camarón y pargo)", "en": "RAS (camarón and snapper)"}, "meal": {"es": "Harinas de subproductos", "en": "By-product meals"},
 "rej": {"es": "Rechazado (enfriador seco)", "en": "Rejected (dry cooler)"},
 "cap_case": {"es": "Caso de capacidad multiproducto (65 %)", "en": "Multi-product capacity case (65%)"},
 "t_year": {"es": "t/año", "en": "t/year"}, "musd": {"es": "Millones de US$/año", "en": "US$ million/year"},
 "fresh_proc": {"es": "Fruta fresca procesada", "en": "Fresh fruit processed"}, "dried": {"es": "Producto seco", "en": "Dried product"},
 "rev_bulk": {"es": "Ingreso (precio a granel)", "en": "Revenue (bulk price)"}, "margin_bulk": {"es": "Margen bruto (granel)", "en": "Gross margin (bulk)"},
 "margin_prem": {"es": "Margen bruto (premium)", "en": "Gross margin (premium)"},
 "usd_t": {"es": "Valor neto (US$/t de fruta fresca)", "en": "Net value (US$/t fresh fruit)"},
 "sun": {"es": "Secado al sol", "en": "Sun drying"}, "sd": {"es": "Secadores Digitales", "en": "Secadores Digitales"},
 "lpg": {"es": "Secador a GLP", "en": "LPG dryer"}, "fresh": {"es": "Venta fresca local", "en": "Local fresh sale"},
 "feas": {"es": "Viabilidad del secado al sol", "en": "Sun-drying feasibility"},
 "loop_pct": {"es": "Proteína de harina de pescado sustituida (%)", "en": "Fishmeal protein replaced (%)"},
 "to_snap": {"es": "Harina de camarones → pargo", "en": "Camarón meal → snapper"}, "to_cam": {"es": "Harina de pargo → camarones", "en": "Snapper meal → camarones"},
 "cases": {"es": ["Real 2020\n(684 t pargo)", "0,1 %\n(3711 t)", "0,5 %\n(18 555 t)", "1 %\n(37 110 t)"],
           "en": ["Actual 2020\n(684 t snapper)", "0.1%\n(3,711 t)", "0.5%\n(18,555 t)", "1%\n(37,110 t)"]},
 "cue": {"es": "Intensidad de carbono (g CO₂/kWh TI)", "en": "Carbon intensity (g CO₂/kWh IT)"},
 "acc": {"es": ["Promedio 2025", "Promedio 2024", "Marginal, año normal", "Marginal, año seco"],
         "en": ["2025 average", "2024 average", "Marginal, normal year", "Marginal, dry year"]},
 "sys": {"es": ["SD interrumpible", "SD estación lluviosa", "SD firme", "Quantum 200 MW", "Palo Negro 38 MW", "Palo Negro 120 MW"],
         "en": ["SD interruptible", "SD rainy-season-led", "SD firm", "Quantum 200 MW", "Palo Negro 38 MW", "Palo Negro 120 MW"]},
 "erf": {"es": "Calor reutilizado (% de la energía de la instalación)", "en": "Heat reused (% of facility energy)"},
 "water": {"es": "Agua declarada (millones de m³/año)", "en": "Declared water use (million m³/year)"},
 "land": {"es": "Terreno (ha por MW TI)", "en": "Land (ha per MW IT)"},
 "jobs": {"es": "Empleos permanentes estimados", "en": "Estimated permanent jobs"},
 "months": {"es": "Meses hasta 10²⁷ FLOP (inicio en junio)", "en": "Months to 10²⁷ FLOP (June start)"},
 "overhead": {"es": "Sobrecarga de comunicación entre sitios (%)", "en": "Inter-site communication overhead (%)"},
 "H": {"es": "Pasos internos entre sincronizaciones (H)", "en": "Inner steps between synchronisations (H)"},
 "tornado": {"es": "Cambio del margen bruto anual (millones de US$)", "en": "Change in annual gross margin (US$ million)"},
 "low": {"es": "Caso bajo", "en": "Low case"},
 "node_heat": {"es": "Calor anual por nodo (GWhₜ)", "en": "Annual heat per node (GWhₜ)"},
 "dry_draw": {"es": "Compra a la red en enero–abril (GWh)", "en": "Grid purchase in January–April (GWh)"},
 "pn_month": {"es": "Palo Negro 38 MW: energía mensual (GWh)", "en": "Palo Negro 38 MW: monthly energy (GWh)"},
 "pv": {"es": "Solar propia", "en": "Own solar"}, "wind": {"es": "Eólica propia", "en": "Own wind"}, "load": {"es": "Demanda de la instalación", "en": "Facility demand"}, "high": {"es": "Caso alto", "en": "High case"},
 "fruit": {"es": "Fruta (mango, piña, banano, plátano)", "en": "Fruit (mango, pineapple, banana, plantain)"},
 "cafe": {"es": "Café pergamino", "en": "Parchment coffee"}, "aquafeed": {"es": "Harinas acuícolas", "en": "Aquafeed meals"},
 "feeds": {"es": "Piensos (harina de banano, rastrojo, pulpa, heno)", "en": "Livestock feed (banana meal, stubble, pulp, hay)"},
 "own_ren": {"es": "Generación propia usada", "en": "Own generation used"}, "grid": {"es": "Compra a la red ICE", "en": "ICE grid purchase"},
}
SENS_LABELS = {
 "Heat-pump dryer capital ±50%": {"es": "Capital de bombas de calor ±50 %", "en": "Heat-pump dryer capital ±50%"},
 "Heat-pump SMER 2–4 kg/kWh": {"es": "SMER de bomba de calor 2–4 kg/kWh", "en": "Heat-pump SMER 2–4 kg/kWh"},
 "Dryer capital and O&M ±50%": {"es": "Capital y O&M del secador ±50 %", "en": "Dryer capital and O&M ±50%"},
 "Feedstock availability ×0.5 / ×2": {"es": "Disponibilidad de materia prima ×0,5 / ×2", "en": "Feedstock availability ×0.5 / ×2"},
 "Bulk vs premium dried price": {"es": "Precio a granel vs premium", "en": "Bulk vs premium dried price"},
 "Processing cost ±30%": {"es": "Costo de procesamiento ±30 %", "en": "Processing cost ±30%"},
 "Feedstock price ±30%": {"es": "Precio de la materia prima ±30 %", "en": "Feedstock price ±30%"},
 "Bulk dried price ±30%": {"es": "Precio a granel ±30 %", "en": "Bulk dried price ±30%"},
}


def t(k, L):
    return T[k][L]


def load():
    R = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    nodes = list(csv.DictReader((OUT / "nodes.csv").open(encoding="utf-8")))
    monthly = list(csv.DictReader((OUT / "monthly_network.csv").open(encoding="utf-8")))
    farmer = list(csv.DictReader((OUT / "farmer_drying_economics.csv").open(encoding="utf-8")))
    sites = {s["id"]: s for s in json.loads((HERE / "data" / "sites.json").read_text(encoding="utf-8"))}
    edges = json.loads((HERE / "data" / "fibre-edges.json").read_text(encoding="utf-8"))
    outline = json.loads((HERE / "data" / "cr_outline.json").read_text(encoding="utf-8"))
    A = json.loads((HERE / "assumptions.json").read_text(encoding="utf-8"))
    return R, nodes, monthly, farmer, sites, edges, outline, A


def fig_map(L, R, nodes, sites, edges, outline, A, d):
    fig, ax = plt.subplots(figsize=(6.6, 5.2))
    for line in outline["coast"]:
        a = np.array(line); ax.plot(a[:, 0], a[:, 1], color="#4a6f8a", lw=0.6)
    for line in outline["borders"]:
        a = np.array(line); ax.plot(a[:, 0], a[:, 1], color="#888", lw=0.6, ls="--")
    CLc = {"norte_guanacaste": "#0088cc", "central_los_santos": "#7b5ea7", "reventazon_caribe": "#c0392b"}
    CLn = {"es": {"norte_guanacaste": "Clúster Norte–Guanacaste", "central_los_santos": "Clúster Central–Los Santos", "reventazon_caribe": "Clúster Reventazón–Caribe"},
           "en": {"norte_guanacaste": "North–Guanacaste cluster", "central_los_santos": "Central–Los Santos cluster", "reventazon_caribe": "Reventazón–Caribbean cluster"}}
    memb = {i: k for k, v in R["clusters"]["clusters"].items() for i in v["nodes"]}
    for a, b in edges:
        A_, B_ = sites[a], sites[b]
        same = memb.get(a) == memb.get(b)
        ax.plot([A_["lon"], B_["lon"]], [A_["lat"], B_["lat"]], color=(CLc[memb[a]] if same else "#999"), lw=(1.4 if same else 0.9),
                ls=("-" if same else "--"), alpha=0.85, zorder=2)
    mw = {int(n["id"]): float(n["it_mw"]) for n in nodes}
    for sc in ("hub", "medium", "small"):
        pts = [int(n["id"]) for n in nodes if n["scale"] == sc]
        ax.scatter([sites[i]["lon"] for i in pts], [sites[i]["lat"] for i in pts], s=[12 + 3.2 * mw[i] for i in pts], color=C[sc],
                   edgecolor="white", lw=0.6, zorder=3, label=t(sc, L))
    for n in nodes:
        s_ = sites[int(n["id"])]
        if n["scale"] == "hub" or int(n["id"]) in (12, 19):
            off = {1: (4, 6), 2: (-34, -11), 27: (-26, 6), 26: (2, -14), 31: (5, 3), 29: (4, -8), 32: (-58, -6), 24: (-20, 7)}.get(int(n["id"]), (4, 3))
            ax.annotate(f"{s_['name']} ({mw[int(n['id'])]:.0f})", (s_["lon"], s_["lat"]), xytext=off, textcoords="offset points", fontsize=6.0)
    for k, col in CLc.items():
        ax.plot([], [], color=col, lw=1.4, label=CLn[L][k])
    Q = A["comparators"]["quantum_limon"]; P = A["comparators"]["palo_negro_bagaces"]
    ax.scatter([Q["lon"]], [Q["lat"]], marker="s", s=110, color=C["q"], zorder=4, label=t("quantum", L))
    ax.scatter([P["lon"]], [P["lat"]], marker="D", s=80, color=C["pn"], zorder=4, label=t("palo", L))
    ax.plot([], [], color="#999", lw=0.9, ls="--", label=("Enlace entre clústeres" if L == "es" else "Inter-cluster link"))
    ax.set_xlim(-86.0, -82.5); ax.set_ylim(8.0, 11.3); ax.set_aspect("equal")
    ax.set_xlabel(t("lon", L)); ax.set_ylabel(t("lat", L))
    ax.legend(loc="lower left", fontsize=6.2, frameon=True, framealpha=0.9)
    fig.savefig(d / "Fig01_mapa_red.png" if L == "es" else d / "Fig01_network_map.png", bbox_inches="tight"); plt.close(fig)


def fig_monthly(L, R, monthly, d):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.0, 2.8), gridspec_kw={"width_ratios": [1.4, 1]})
    x = np.arange(12)
    for case, col, ls in (("firm", "#555", "-"), ("normal", C["sd"], "-"), ("dry_year", C["sun"], "--"), ("seasonal", C["ras"], "-.")):
        y = [float(r["it_gwh"]) for r in monthly if r["case"] == case]
        a1.plot(x, y, color=col, ls=ls, marker="o", ms=2.5, label=t(case, L))
    a1.set_xticks(x); a1.set_xticklabels(MES[L]); a1.set_ylabel(t("it_month", L)); a1.legend(fontsize=6.3, frameon=False)
    a1.set_title("a")
    F = R["grid_factors_kg_per_kwh"]
    a2.bar(x - 0.2, F["marg_normal"], 0.4, color=C["sd"], label=t("marg_normal", L))
    a2.bar(x + 0.2, F["marg_dry_year"], 0.4, color=C["sun"], label=t("marg_dry_year", L))
    a2.set_xticks(x); a2.set_xticklabels(MES[L]); a2.set_ylabel(t("marg", L)); a2.legend(fontsize=6.3, frameon=False); a2.set_title("b")
    fig.tight_layout(); fig.savefig(d / ("Fig02_perfil_mensual.png" if L == "es" else "Fig02_monthly_profile.png"), bbox_inches="tight"); plt.close(fig)


GROUPS = {"fruit": ["mango", "pina", "banano", "platano"], "cafe": ["cafe"], "aquafeed": ["harinas"],
          "feeds": ["harina_banano", "rastrojo_pina", "pulpa_cafe", "heno_pasto"]}
GCOL = {"fruit": "#e8a33d", "cafe": "#6f4e37", "aquafeed": "#7b5ea7", "feeds": "#9bbf4a"}


def fig_heat(L, R, d):
    fig, (ax, a2) = plt.subplots(1, 2, figsize=(7.6, 3.0), gridspec_kw={"width_ratios": [1.6, 1]})
    cases = ["normal", "dry_year", "seasonal", "firm"]
    for i, c in enumerate(cases):
        tot = R["totals"][c]; prod = R["products_by_case"][c]
        parts = [("ras", tot["ras_heat_gwh"], C["ras"])]
        for g, ks in GROUPS.items():
            parts.append((g, sum(prod[k]["heat_mwh"] for k in ks) / 1000, GCOL[g]))
        parts.append(("rej", tot["rejected_heat_gwh"], C["rej"]))
        left = 0
        for k, v, col in parts:
            ax.barh(i, v, left=left, color=col, label=t(k, L) if i == 0 else None, edgecolor="white", lw=0.4)
            left += v
        lab = f"{tot['reused_pct_of_heat']:.0f} % · ERF {tot['erf_pct']:.0f} %" if L == "es" else f"{tot['reused_pct_of_heat']:.0f}% · ERF {tot['erf_pct']:.0f}%"
        ax.text(left + 20, i, lab, va="center", fontsize=6.0)
    cap = R["website_capacity_case"]["heat_mwh"] / 1000
    ax.axvline(cap, color="#333", ls=":", lw=1); ax.text(cap, -0.75, t("cap_case", L), fontsize=5.8, ha="center")
    ax.set_yticks(range(len(cases))); ax.set_yticklabels([t(c, L) for c in cases], fontsize=6.6); ax.invert_yaxis()
    ax.set_xlabel(t("gwh_th", L)); ax.set_xlim(0, 1.45 * max(R["totals"][c]["heat_gwh"] for c in cases)); ax.set_title("a", loc="left")
    ax.legend(ncol=2, fontsize=5.8, frameon=False, loc="upper center", bbox_to_anchor=(0.6, -0.2))
    M = R["monthly_heat"]["normal"]; x = np.arange(12)
    ras = np.array(M["ras"]) / 1000; dry = np.array(M["dry"]) / 1000; rej = np.array(M["rejected"]) / 1000
    a2.bar(x, ras, color=C["ras"], label="RAS"); a2.bar(x, dry, bottom=ras, color="#c9a227", label=("Secado" if L == "es" else "Drying"))
    a2.bar(x, rej, bottom=ras + dry, color=C["rej"], label=("Rechazo" if L == "es" else "Rejected")); a2.set_ylim(0, 1.3 * float(np.max(ras + dry + rej)))
    a2.set_xticks(x); a2.set_xticklabels(MES[L]); a2.set_ylabel(("Calor mensual (GWhₜ)" if L == "es" else "Monthly heat (GWhₜ)"))
    a2.set_title("b", loc="left"); a2.legend(fontsize=6, frameon=False, loc="upper left", ncol=3)
    fig.tight_layout(); fig.savefig(d / ("Fig03_cascada_calor.png" if L == "es" else "Fig03_heat_cascade.png"), bbox_inches="tight"); plt.close(fig)


PNAME = {"es": {"mango": "Mango", "pina": "Piña", "banano": "Banano", "platano": "Plátano", "harinas": "Harinas acuícolas",
                "cafe": "Café pergamino", "harina_banano": "Harina de banano", "rastrojo_pina": "Rastrojo de piña",
                "pulpa_cafe": "Pulpa de café", "heno_pasto": "Heno de pasto"},
         "en": {"mango": "Mango", "pina": "Pineapple", "banano": "Banana", "platano": "Plantain", "harinas": "Aquafeed meals",
                "cafe": "Parchment coffee", "harina_banano": "Banana meal", "rastrojo_pina": "Pineapple stubble",
                "pulpa_cafe": "Coffee pulp", "heno_pasto": "Pasture hay"}}
PORDER = ["mango", "pina", "banano", "platano", "harinas", "cafe", "harina_banano", "rastrojo_pina", "pulpa_cafe", "heno_pasto"]


def pcol(k):
    for g, ks in GROUPS.items():
        if k in ks:
            return GCOL[g]


def fig_products(L, R, A, d):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.2), sharey=True)
    P = R["products"]; ks = PORDER; y = np.arange(len(ks))
    a1.barh(y - 0.2, [P[k]["water_removed_t"] / 1000 for k in ks], 0.4, color="#9cc", label=("Agua evaporada" if L == "es" else "Water evaporated"))
    a1.barh(y + 0.2, [P[k]["dried_t"] / 1000 for k in ks], 0.4, color=[pcol(k) for k in ks], label=t("dried", L))
    un = [P[k]["unprocessed_t"] / 1000 for k in ks]
    xa = max(max(P[k]["water_removed_t"], P[k]["dried_t"]) for k in ks) / 1000
    for i, k in enumerate(ks):
        if un[i] > 0.5:
            a1.text(P[k]["water_removed_t"] / 1000 + 0.015 * xa, i - 0.2, (f"sin secar: {un[i]:.0f} kt" if L == "es" else f"undried: {un[i]:.0f} kt"), fontsize=5.6, va="center")
    a1.set_yticks(y); a1.set_yticklabels([PNAME[L][k] for k in ks], fontsize=6.6); a1.invert_yaxis()
    a1.set_xlabel(("Miles de t/año" if L == "es" else "Thousand t/year")); a1.set_xlim(0, 1.45 * xa); a1.legend(fontsize=6, frameon=False, loc="upper right"); a1.set_title("a", loc="left")
    m = [P[k]["gross_margin_usd"] / 1e6 for k in ks]
    a2.barh(y, m, color=[pcol(k) for k in ks]); a2.axvline(0, color="#333", lw=0.7)
    for i, k in enumerate(ks):
        be = P[k]["breakeven_price_usd_kg"]
        txt = f"{m[i]:.1f}" + (f" · eq. US${be:.2f}/kg" if (be is not None and k in GROUPS["feeds"]) else "")
        if k == "cafe":
            txt = "servicio al costo" if L == "es" else "service at cost"
        if L == "es":
            txt = txt.replace(".", ",").replace("eq,", "equil.")
        a2.text(max(m[i], 0) + 0.4, i, txt, va="center", fontsize=5.8)
    a2.set_xlabel(("Margen bruto (millones de US$/año)" if L == "es" else "Gross margin (US$ million/year)")); a2.set_xlim(min(-4, 1.15 * min(m)), max(30, 1.6 * max(m))); a2.set_title("b", loc="left")
    fig.tight_layout(); fig.savefig(d / ("Fig04_productos_secos.png" if L == "es" else "Fig04_dried_products.png"), bbox_inches="tight"); plt.close(fig)


def fig_dryers(L, R, d):
    D = R["dryer_designs"]; ks = ["open", "hybrid", "food_hp", "hp_all"]
    names = {"es": ["Aire\nabierto", "Híbrido\n(central)", "BC en\nfruta", "BC en\ntodo"],
             "en": ["Open\nair", "Hybrid\n(central)", "HP on\nfruit", "HP on\neverything"]}[L]
    cols = ["#c9a227", C["sd"], "#2b7bb9", "#5b3a8c"]
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.9)); x = np.arange(4)
    a = axs[0]
    a.bar(x, [D[k]["reused_pct_of_heat"] for k in ks], color=cols)
    for i, k in enumerate(ks):
        a.text(i, D[k]["reused_pct_of_heat"] + 1.5, f"{D[k]['reused_pct_of_heat']:.0f}", ha="center", fontsize=6.2)
    a.set_ylabel(("Calor residual reutilizado (%)" if L == "es" else "Waste heat reused (%)")); a.set_ylim(0, 100)
    a.set_xticks(x); a.set_xticklabels(names, fontsize=6.2); a.set_title("a", loc="left")
    a = axs[1]
    a.bar(x - 0.2, [D[k]["drying_energy_efficiency_pct"] for k in ks], 0.4, color=cols, alpha=0.55, label=("Eficiencia de secado (%)" if L == "es" else "Drying efficiency (%)"))
    a.bar(x + 0.2, [D[k]["drying_elec_gwh"] for k in ks], 0.4, color=cols, hatch="///", edgecolor="white", label=("Electricidad de secado (GWh)" if L == "es" else "Drying electricity (GWh)"))
    a.set_xticks(x); a.set_xticklabels(names, fontsize=6.2); a.legend(fontsize=5.6, frameon=False, loc="upper left"); a.set_title("b", loc="left"); a.set_ylim(0, 200)
    a = axs[2]
    v = [(D[k]["margin_usd"] + D[k]["water_value_usd"]) / 1e6 for k in ks]
    a.bar(x, v, color=cols); a.axhline(0, color="#333", lw=0.7)
    for i, y_ in enumerate(v):
        a.text(i, (y_ + 1.5) if y_ >= 0 else 2, (f"{y_:.1f}".replace(".", ",") if L == "es" else f"{y_:.1f}"), ha="center", fontsize=6.2)
    a.set_ylabel(("Margen + agua destilada (M US$/año)" if L == "es" else "Margin + distilled water (US$ M/yr)"))
    a.set_xticks(x); a.set_xticklabels(names, fontsize=6.2); a.set_title("c", loc="left"); a.set_ylim(-48, 48)
    fig.tight_layout(); fig.savefig(d / ("Fig14_tecnologia_secado.png" if L == "es" else "Fig14_dryer_technology.png"), bbox_inches="tight"); plt.close(fig)


def fig_farmer(L, farmer, d):
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.7), sharey=False)
    for ax, (prod, zone, title) in zip(axs, (("mango", "PN", "a"), ("banano", "CA", "b"), ("platano", "ZN", "c"))):
        rows = [r for r in farmer if r["product"] == prod and r["zone"] == zone]
        rows.sort(key=lambda r: int(r["month"]))
        x = np.arange(12)
        ax2 = ax.twinx()
        ax2.bar(x, [float(r["sun_feasibility"]) for r in rows], color="#f3d9a6", alpha=0.6, width=0.8, zorder=0)
        ax2.set_ylim(0, 1); ax2.set_yticks([0, 0.5, 1]); ax2.tick_params(labelsize=6)
        if title == "c":
            ax2.set_ylabel(t("feas", L), fontsize=7)
        ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
        for key, col, lab in (("secadores_net_usd_t", C["sd"], "sd"), ("lpg_net_usd_t", C["lpg"], "lpg"), ("fresh_sale_usd_t", C["fresh"], "fresh"), ("sun_net_usd_t", C["sun"], "sun")):
            ax.plot(x, [float(r[key]) for r in rows], color=col, marker="o", ms=2.2, lw=1.2, label=t(lab, L))
        ax.set_xticks(x); ax.set_xticklabels(MES[L], fontsize=6.3)
        zn = {"PN": "Pacífico Norte", "CA": "Caribe", "ZN": "Zona Norte"}[zone]
        ax.set_title(f"{title}  {t(prod, L)} · {zn}")
        if title == "a":
            ax.set_ylabel(t("usd_t", L))
    axs[0].legend(fontsize=5.8, frameon=False, loc="center left")
    fig.tight_layout(); fig.savefig(d / ("Fig05_economia_agricultores.png" if L == "es" else "Fig05_farmer_economics.png"), bbox_inches="tight"); plt.close(fig)


def fig_loop(L, R, d):
    fig, ax = plt.subplots(figsize=(5.6, 2.7))
    keys = ["actual_2020", "0.1pct", "0.5pct", "1pct"]; x = np.arange(4)
    Lp = R["circular_loop"]
    ax.bar(x - 0.2, [Lp[k]["camaron_fishmeal_protein_replaced_pct"] for k in keys], 0.4, color=C["ras"], label=t("to_cam", L))
    ax.bar(x + 0.2, [Lp[k]["snapper_fishmeal_protein_replaced_pct"] for k in keys], 0.4, color=C["meal"], label=t("to_snap", L))
    for i, k in enumerate(keys):
        ax.text(i - 0.2, Lp[k]["camaron_fishmeal_protein_replaced_pct"] + 1, f"{Lp[k]['camaron_fishmeal_protein_replaced_pct']:.0f}", ha="center", fontsize=6.3)
        ax.text(i + 0.2, Lp[k]["snapper_fishmeal_protein_replaced_pct"] + 1, f"{Lp[k]['snapper_fishmeal_protein_replaced_pct']:.1f}", ha="center", fontsize=6.3)
    ax.set_xticks(x); ax.set_xticklabels(T["cases"][L], fontsize=6.5); ax.set_ylabel(t("loop_pct", L)); ax.set_ylim(0, 60)
    ax.legend(fontsize=6.5, frameon=False)
    fig.tight_layout(); fig.savefig(d / ("Fig06_ciclo_camarones_pargo.png" if L == "es" else "Fig06_camaron_snapper_loop.png"), bbox_inches="tight"); plt.close(fig)


SYS = ["secadores_normal", "secadores_seasonal", "secadores_firm", "quantum_limon", "palo_negro_38mw", "palo_negro_120mw"]
SYSC = [C["sd"], C["ras"], "#7aa", C["q"], C["pn"], "#e0b46a"]


def fig_carbon(L, R, d):
    fig, ax = plt.subplots(figsize=(7.0, 2.9))
    accs = ["avg_2025", "avg_2024", "marg_normal", "marg_dry_year"]; x = np.arange(4); w = 0.13
    for j, s in enumerate(SYS):
        v = [R["comparison"][s]["cue_g_per_kwh_it"][a] for a in accs]
        ax.bar(x + (j - 2.5) * w, v, w, color=SYSC[j], label=T["sys"][L][j])
    ax.set_xticks(x); ax.set_xticklabels(T["acc"][L]); ax.set_ylabel(t("cue", L)); ax.legend(fontsize=6.1, ncol=3, frameon=False)
    fig.tight_layout(); fig.savefig(d / ("Fig07_carbono.png" if L == "es" else "Fig07_carbon.png"), bbox_inches="tight"); plt.close(fig)


def fig_compare(L, R, d):
    fig, axs = plt.subplots(2, 2, figsize=(6.4, 5.0)); axs = axs.ravel()
    S4 = ["secadores_normal", "quantum_limon", "palo_negro_38mw"]
    lab = ["Secadores\nDigitales", "Quantum\n(200 MW)", "Palo Negro\n(38 MW)"]
    cols = [C["sd"], C["q"], C["pn"]]
    Cm = R["comparison"]
    vals = {"erf": [100 * Cm[s]["erf"] for s in S4], "water": [Cm[s]["cooling_water_m3"] / 1e6 for s in S4],
            "jobs": [sum(Cm["secadores_normal"]["jobs_fte"].values()), float("nan"), 100.0]}
    titles = {"erf": t("erf", L).replace(" (", "\n("), "water": ("Agua de enfriamiento: disponibilidad declarada\n(millones de m³/año; límite superior)" if L == "es" else "Cooling water: declared availability\n(million m³/year; upper bound)"),
              "jobs": t("jobs", L)}
    for ax, k, letter in zip([axs[0], axs[1], axs[3]], ["erf", "water", "jobs"], "abd"):
        v = vals[k]
        ax.bar(range(3), v, color=cols)
        for i, y in enumerate(v):
            tx = ("n/d" if np.isnan(y) else (f"{y:.1f}" if y < 50 else f"{y:.0f}"))
            ax.text(i, (0 if np.isnan(y) else y), tx.replace(".", ",") if L == "es" else tx, ha="center", va="bottom", fontsize=6.3)
        ax.set_xticks(range(3)); ax.set_xticklabels(lab, fontsize=6.6)
        ax.set_title(f"{letter}  {titles[k]}", fontsize=6.6, loc="left")
    ax = axs[2]
    dirv = [Cm[s]["land_direct_ha"] / Cm[s]["it_mw"] for s in S4]; genv = [Cm[s]["land_new_generation_ha"] / Cm[s]["it_mw"] for s in S4]
    ax.bar(range(3), dirv, color=cols, label=("Instalaciones" if L == "es" else "Facilities"))
    ax.bar(range(3), genv, bottom=dirv, color=cols, alpha=0.4, hatch="//", label=("Generación nueva" if L == "es" else "New generation"))
    for i in range(3):
        tx = f"{dirv[i] + genv[i]:.2f}"; ax.text(i, dirv[i] + genv[i], tx.replace(".", ",") if L == "es" else tx, ha="center", va="bottom", fontsize=6.3)
    ax.set_xticks(range(3)); ax.set_xticklabels(lab, fontsize=6.6); ax.legend(fontsize=5.8, frameon=False, loc="upper left")
    ax.set_title("c  " + ("Terreno por MW de TI (ha)\nhidroeléctricas existentes no atribuidas" if L == "es" else "Land per IT MW (ha)\nexisting hydro not attributed"), fontsize=6.6, loc="left")
    fig.tight_layout(); fig.savefig(d / ("Fig08_comparacion.png" if L == "es" else "Fig08_comparison.png"), bbox_inches="tight"); plt.close(fig)


def fig_massflow(L, R, d):
    P = R["products"]; ks = PORDER
    fig, ax = plt.subplots(figsize=(7.0, 3.2)); y = np.arange(len(ks))
    dried = np.array([P[k]["dried_t"] for k in ks]) / 1000; water = np.array([P[k]["water_removed_t"] for k in ks]) / 1000
    rem = np.array([P[k]["pretreatment_removed_t"] for k in ks]) / 1000
    ax.barh(y, dried, color="#1f7a5a", label=("Producto seco" if L == "es" else "Dried product"))
    ax.barh(y, water, left=dried, color="#9cc", label=("Agua evaporada" if L == "es" else "Water evaporated"))
    ax.barh(y, rem, left=dried + water, color="#c9a227", label=("Retirado en pretratamiento (cáscara, semilla o líquido de prensa)" if L == "es" else "Removed in pretreatment (peel, seed or press liquid)"))
    xmax = float(max(P[k]["fresh_processed_t"] for k in ks) / 1000)
    for i, k in enumerate(ks):
        tot = P[k]["fresh_processed_t"] / 1000
        ax.text(tot + 0.01 * xmax, i, (f"{tot:,.0f} kt frescas" if L == "es" else f"{tot:,.0f} kt fresh").replace(",", " " if L == "es" else ","), va="center", fontsize=5.8)
    ax.set_yticks(y); ax.set_yticklabels([PNAME[L][k] for k in ks], fontsize=6.6); ax.invert_yaxis()
    ax.set_xlabel(("Miles de t/año" if L == "es" else "Thousand t/year")); ax.set_xlim(0, 1.22 * xmax); ax.legend(fontsize=5.8, frameon=False, loc="lower right")
    fig.tight_layout(); fig.savefig(d / ("FigS3_flujo_masa.png" if L == "es" else "FigS3_mass_flow.png"), bbox_inches="tight"); plt.close(fig)


def fig_training(L, R, d):
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(7.4, 2.8), gridspec_kw={"width_ratios": [1.5, 1, 1]})
    sy = ["secadores_net_normal", "secadores_net_seasonal", "secadores_200mw_normal", "quantum_200mw", "palo_negro_38mw", "palo_negro_120mw"]
    names = {"es": ["SD\n400", "SD 400\nlluv.", "SD\n200", "Quan-\ntum\n200", "Palo\nNegro\n38", "Palo\nNegro\n120"],
             "en": ["SD\n400", "SD 400\nrainy", "SD\n200", "Quan-\ntum\n200", "Palo\nNegro\n38", "Palo\nNegro\n120"]}
    x = np.arange(len(sy)); S = R["training"]["systems"]
    g1 = [S[f"{s}|gb300_nvl72"]["months_to_target_start_june"] for s in sy]
    g2 = [S[f"{s}|vera_rubin_nvl144"]["months_to_target_start_june"] for s in sy]
    a1.bar(x - 0.2, g1, 0.4, color="#76b900", label="GB300 NVL72"); a1.bar(x + 0.2, g2, 0.4, color="#3a5a00", label="Vera Rubin NVL144")
    for i in range(len(sy)):
        a1.text(i - 0.2, g1[i] + 0.2, (f"{g1[i]:.1f}".replace(".", ",") if L == "es" else f"{g1[i]:.1f}"), ha="center", fontsize=5.4)
    a1.set_xticks(x); a1.set_xticklabels(names[L], fontsize=5.4); a1.set_ylabel(t("months", L), fontsize=6.6); a1.legend(fontsize=5.8, frameon=False); a1.set_title("a", loc="left")
    Hs = [1, 10, 100, 500]
    a2.plot(Hs, [100 * S["secadores_net_normal|gb300_nvl72"]["overhead_by_H"][str(h)] for h in Hs], marker="o", ms=3, color="#333", label=("Red completa" if L == "es" else "Whole network"))
    CLc = {"norte_guanacaste": "#0088cc", "central_los_santos": "#7b5ea7", "reventazon_caribe": "#c0392b"}
    CLs = {"es": {"norte_guanacaste": "Norte–\nGuanacaste", "central_los_santos": "Central–\nLos Santos", "reventazon_caribe": "Reventazón–\nCaribe"},
           "en": {"norte_guanacaste": "North–\nGuanacaste", "central_los_santos": "Central–\nLos Santos", "reventazon_caribe": "Reventazón–\nCaribbean"}}
    CL = R["clusters"]["clusters"]
    for k, col in CLc.items():
        a2.plot(Hs, [100 * CL[k]["overhead_by_H"][str(h)] for h in Hs], marker="s", ms=2.5, color=col, label=CLs[L][k])
    a2.set_xscale("log"); a2.set_yscale("log"); a2.set_xlabel(t("H", L), fontsize=6.4); a2.set_ylabel(t("overhead", L), fontsize=6.4); a2.legend(fontsize=5.4, frameon=False); a2.set_title("b", loc="left")
    xs = np.arange(3); ks = list(CLc)
    a3.bar(xs - 0.2, [CL[k]["models_per_year"] for k in ks], 0.4, color=[CLc[k] for k in ks], label=("Año normal" if L == "es" else "Normal year"))
    a3.bar(xs + 0.2, [R["clusters_seasonal"]["clusters"][k]["models_per_year"] for k in ks], 0.4, color=[CLc[k] for k in ks], alpha=0.45,
           label=("Estación lluviosa" if L == "es" else "Rainy-season-led"))
    a3.set_xticks(xs); a3.set_xticklabels([CLs[L][k] for k in ks], fontsize=5.4)
    a3.set_ylabel(("Modelos de 3×10²⁶ FLOP por año" if L == "es" else "3×10²⁶-FLOP models per year"), fontsize=6.4); a3.set_ylim(0, 16); a3.legend(fontsize=5.4, frameon=False, loc="upper left"); a3.set_title("c", loc="left")
    fig.tight_layout(); fig.savefig(d / ("Fig09_entrenamiento.png" if L == "es" else "Fig09_training.png"), bbox_inches="tight"); plt.close(fig)


def fig_econ(L, R, d):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={"width_ratios": [1.35, 1]})
    E = R["economics"]["central"]; EC = R["economics_conservative"]
    ks = ["secadores_normal", "secadores_seasonal", "secadores_firm", "quantum_limon", "palo_negro_38mw", "palo_negro_120mw"]
    nm = {"es": ["SD 400 MW\ninterrump.", "SD 400 MW\nlluviosa", "SD 400 MW\nfirme", "Quantum\n200 MW", "Palo Negro\n38 MW", "Palo Negro\n120 MW"],
          "en": ["SD 400 MW\ninterrupt.", "SD 400 MW\nrainy", "SD 400 MW\nfirm", "Quantum\n200 MW", "Palo Negro\n38 MW", "Palo Negro\n120 MW"]}[L]
    x = np.arange(len(ks)); w = 0.2
    a1.bar(x - 1.5 * w, [E[k]["ebitda_usd"] / 1e9 for k in ks], w, color=C["sd"], label=("EBITDA central" if L == "es" else "Central EBITDA"))
    a1.bar(x - 0.5 * w, [EC[k]["ebitda_usd"] / 1e9 for k in ks], w, color="#86bf3f", label=("EBITDA comercial conservador" if L == "es" else "Conservative commercial EBITDA"))
    a1.bar(x + 0.5 * w, [E[k]["capital_charge_wacc_usd"] / 1e9 for k in ks], w, color="#999", label=("Cargo de capital (9 %)" if L == "es" else "Capital charge (9%)"))
    a1.bar(x + 1.5 * w, [E[k]["community_funded_usd"] / 1e9 for k in ks], w, color="#e8a33d", label=("Comunidad financiada (≤10 % EBITDA)" if L == "es" else "Community funded (≤10% EBITDA)"))
    a1.set_xticks(x); a1.set_xticklabels(nm, fontsize=5.6); a1.set_ylabel(("Miles de millones de US$/año" if L == "es" else "US$ billion/year"), fontsize=6.6)
    a1.legend(fontsize=5.4, frameon=False); a1.set_title("a", loc="left")
    cs = ["secadores_normal", "secadores_seasonal", "secadores_firm", "quantum_limon"]
    lab = {"es": ["SD interrump.", "SD lluviosa", "SD firme", "Quantum"], "en": ["SD interrupt.", "SD rainy", "SD firm", "Quantum"]}[L]
    xs = np.arange(len(cs))
    dc = [E[k]["ebitda_less_capital_charge_usd"] / 1e9 for k in cs]
    dk = [EC[k]["distributable_usd"] / 1e9 for k in cs]
    tg = [E[k]["community_10pct_usd"] / 1e9 for k in cs]
    a2.bar(xs - 0.2, dc, 0.4, color=C["sd"], label=("Caja tras cargo de capital, central" if L == "es" else "Cash after capital charge, central"))
    a2.bar(xs + 0.2, dk, 0.4, color="#86bf3f", label=("Ídem, conservador (con impuesto)" if L == "es" else "Same, conservative (after tax)"))
    a2.scatter(xs - 0.2, tg, marker="_", s=260, color="#e8a33d", zorder=3, label=("Meta comunitaria (10 % EBITDA)" if L == "es" else "Community target (10% EBITDA)"))
    a2.axhline(0, color="#333", lw=0.7)
    for i, k in enumerate(cs):
        for jj, v, src in ((-0.2, dc[i], E[k]), (0.2, dk[i], EC[k])):
            ok = src["community_funded_usd"] > 0
            t_ = ("financiado" if ok else "suspendido") if L == "es" else ("funded" if ok else "suspended")
            a2.text(i + jj, (v + 0.08) if v >= 0 else (v - 0.08), t_, ha="center", va="bottom" if v >= 0 else "top", fontsize=4.4)
    a2.set_xticks(xs); a2.set_xticklabels(lab, fontsize=6.0)
    a2.set_ylabel(("Miles de millones de US$/año" if L == "es" else "US$ billion/year"), fontsize=6.4)
    a2.set_ylim(min(dk) - 0.7, max(max(dc), max(tg)) + 1.6)
    a2.legend(fontsize=5.0, frameon=False, loc="upper right"); a2.set_title("b", loc="left")
    fig.tight_layout(); fig.savefig(d / ("Fig15_economia_comunidad.png" if L == "es" else "Fig15_economics_community.png"), bbox_inches="tight"); plt.close(fig)


def fig_tornado(L, R, d):
    S = sorted(R["sensitivity"], key=lambda r: max(abs(r["low"]), abs(r["high"])))
    fig, ax = plt.subplots(figsize=(6.0, 2.6))
    y = np.arange(len(S))
    ax.barh(y, [r["low"] / 1e6 for r in S], color="#c96", label=t("low", L))
    ax.barh(y, [r["high"] / 1e6 for r in S], color=C["sd"], label=t("high", L))
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_yticks(y); ax.set_yticklabels([SENS_LABELS[r["label"]][L] for r in S], fontsize=6.6)
    ax.set_xlabel(t("tornado", L)); ax.legend(fontsize=6.3, frameon=False, loc="lower right")
    fig.tight_layout(); fig.savefig(d / ("Fig10_sensibilidad.png" if L == "es" else "Fig10_sensitivity.png"), bbox_inches="tight"); plt.close(fig)


def fig_nodes(L, nodes, d):
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    x = np.arange(len(nodes))
    dry = np.array([float(n["drying_heat_gwh"]) for n in nodes]); ras = np.array([float(n["ras_heat_gwh"]) for n in nodes])
    rej = np.array([float(n["rejected_heat_gwh"]) for n in nodes])
    ax.bar(x, dry, color="#c9a227", label=("Secado (café, fruta, harinas, piensos)" if L == "es" else "Drying (coffee, fruit, meals, feed)"))
    ax.bar(x, ras, bottom=dry, color=C["ras"], label=t("ras", L))
    ax.bar(x, rej, bottom=dry + ras, color=C["rej"], label=t("rej", L))
    ax.set_xticks(x); ax.set_xticklabels([f"{n['id']} {n['name'][:11]}" for n in nodes], rotation=90, fontsize=5.6)
    ax.set_ylabel(t("node_heat", L)); ax.legend(fontsize=6.3, frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(); fig.savefig(d / ("Fig11_calor_por_nodo.png" if L == "es" else "Fig11_heat_by_node.png"), bbox_inches="tight"); plt.close(fig)


def fig_dryseason(L, R, d):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.0, 2.8), gridspec_kw={"width_ratios": [1, 1.3]})
    keys = ["secadores_seasonal", "secadores_normal", "secadores_firm", "quantum_limon", "palo_negro_38mw", "palo_negro_120mw"]
    v = [R["comparison"][k]["dry_season_grid_gwh"] for k in keys]
    names = [T["sys"][L][1], T["sys"][L][0], T["sys"][L][2], T["sys"][L][3], T["sys"][L][4], T["sys"][L][5]]
    cols = [C["ras"], C["sd"], "#7aa", C["q"], C["pn"], "#e0b46a"]
    a1.barh(range(len(keys)), v, color=cols); a1.set_yticks(range(len(keys))); a1.set_yticklabels(names, fontsize=6.3); a1.invert_yaxis()
    for i, y in enumerate(v):
        a1.text(y + 5, i, f"{y:.0f}", va="center", fontsize=6.2)
    a1.set_xlabel(t("dry_draw", L)); a1.set_title("a")
    m = R["comparison"]["palo_negro_38mw"]; x = np.arange(12)
    a2.bar(x, m["monthly_pv_gwh"], color="#f2c14e", label=t("pv", L))
    a2.bar(x, m["monthly_wind_gwh"], bottom=m["monthly_pv_gwh"], color="#7fb3d5", label=t("wind", L))
    a2.plot(x, m["monthly_load_gwh"], color="#333", marker="o", ms=2.5, label=t("load", L))
    a2.plot(x, m["monthly_grid_gwh"], color=C["q"], marker="s", ms=2.5, label=t("grid", L))
    a2.set_xticks(x); a2.set_xticklabels(MES[L]); a2.set_ylabel(t("pn_month", L), fontsize=7); a2.set_ylim(0, 42); a2.legend(fontsize=6, frameon=False, ncol=2, loc="upper center"); a2.set_title("b")
    fig.tight_layout(); fig.savefig(d / ("Fig12_estacion_seca.png" if L == "es" else "Fig12_dry_season.png"), bbox_inches="tight"); plt.close(fig)


def fig_era5(L, R, A, d):
    E = R.get("era5"); pn = R["comparison"]["palo_negro_38mw"]
    if not E or "per_year" not in pn:
        return
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(7.6, 3.1), gridspec_kw={"width_ratios": [1.35, 1.1, 1]})
    regs = [("C_caribe_norte", "#2b7bb9", {"es": "Caribe/Zona Norte", "en": "Caribbean/Northern Zone"}),
            ("P_pacifico", "#c98a2b", {"es": "Pacífico", "en": "Pacific"}),
            ("R_embalse_arenal", "#249b59", {"es": "Embalse Arenal", "en": "Arenal reservoir"})]
    x = np.arange(12); w = 0.27
    a1b = a1.twinx()
    for i, (k, col, lab) in enumerate(regs):
        g = E["regimes"][k]
        a1.bar(x + (i - 1) * w, g["monthly_precip_mm"], width=w, color=col, alpha=0.75, label=f"{lab[L]} (r = {g['corr_precip_vs_permission']:.2f})".replace(".", "," if L == "es" else "."))
        a1b.plot(x, np.array(g["permission_profile"]) * 100, color=col, lw=1.3, marker="o", ms=2)
    a1.set_xticks(x); a1.set_xticklabels(MES[L]); a1.set_ylabel("Precipitación ERA5 (mm/mes)" if L == "es" else "ERA5 precipitation (mm/month)")
    a1b.set_ylabel("TI permitida (%)" if L == "es" else "Permitted IT (%)"); a1b.set_ylim(0, 110); a1b.spines["right"].set_visible(True)
    a1.set_ylim(0, 1.45 * max(max(E["regimes"][k]["monthly_precip_mm"]) for k, _, _ in regs))
    a1.legend(fontsize=5.6, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=1); a1.set_title("a", loc="left")
    py = pn["per_year"]; yrs = [p["year"] for p in py]
    a2.plot(yrs, [100 * p["wind_cf"] for p in py], color="#7fb3d5", marker="o", ms=2.5, label=("ERA5 corregido" if L == "es" else "ERA5, bias-corrected"))
    W = pn["wind_calibration"]
    oy = sorted(W["per_year"]); a2.scatter([int(y) for y in oy], [100 * W["per_year"][y]["observed_cf"] for y in oy], color="#b0413e", zorder=3, s=14,
                                            label=("Parque nacional observado" if L == "es" else "National fleet, observed"))
    a2.axhline(100 * W["raw_era5_cf"], color="#888", ls=":", lw=1)
    a2.text(yrs[0], 100 * W["raw_era5_cf"] + 1.5, ("ERA5 sin corregir" if L == "es" else "ERA5, uncorrected"), fontsize=5.6, color="#555")
    a2.set_ylim(0, 65); a2.set_ylabel("Factor de planta eólico (%)" if L == "es" else "Wind capacity factor (%)")
    a2.set_xticks([2010, 2013, 2016, 2019, 2022, 2025]); a2.tick_params(axis="x", labelsize=6.5); a2.legend(fontsize=5.6, frameon=False, loc="upper right"); a2.set_title("b", loc="left")
    a3.plot(x, 100 * np.array(pn["monthly_wind_cf"]), color="#7fb3d5", marker="o", ms=2.5, label=t("wind", L))
    a3.plot(x, 100 * np.array(pn["monthly_pv_cf"]), color="#f2c14e", marker="s", ms=2.5, label=t("pv", L))
    a3.set_xticks(x); a3.set_xticklabels(MES[L]); a3.set_ylim(0, 100); a3.set_ylabel("Factor de planta (%)" if L == "es" else "Capacity factor (%)")
    a3.legend(fontsize=6, frameon=False, loc="upper center"); a3.set_title("c", loc="left")
    fig.tight_layout(); fig.savefig(d / ("FigS8_validacion_era5.png" if L == "es" else "FigS8_era5_validation.png"), bbox_inches="tight"); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--lang", default="both"); a = ap.parse_args()
    R, nodes, monthly, farmer, sites, edges, outline, A = load()
    for L in (["es", "en"] if a.lang == "both" else [a.lang]):
        d = OUT / f"figuras_{L}"; d.mkdir(parents=True, exist_ok=True)
        fig_map(L, R, nodes, sites, edges, outline, A, d); fig_monthly(L, R, monthly, d); fig_heat(L, R, d)
        fig_products(L, R, A, d); fig_farmer(L, farmer, d); fig_loop(L, R, d); fig_carbon(L, R, d)
        fig_compare(L, R, d); fig_training(L, R, d); fig_tornado(L, R, d)
        fig_nodes(L, nodes, d); fig_dryseason(L, R, d); fig_dryers(L, R, d); fig_econ(L, R, d); fig_massflow(L, R, d); fig_era5(L, R, A, d)
    print("figures written")


if __name__ == "__main__":
    main()


def fig_schematic(L, d):
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    es = L == "es"
    fig, ax = plt.subplots(figsize=(7.2, 3.6)); ax.set_xlim(0, 100); ax.set_ylim(0, 52); ax.axis("off")
    def box(x, y, w, h, text, col):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5", fc=col, ec="#333", lw=0.8))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=6.2)
    def arrow(x1, y1, x2, y2, col="#333"):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9, lw=1.1, color=col))
    box(1, 35, 15, 11, "Central\nhidroeléctrica\n(ICE/CNFL/coop.)" if es else "Hydroelectric\nplant\n(ICE/CNFL/coop.)", "#cfe8f3")
    box(23, 35, 17, 11, "Nodo de TI 1–64 MW\nGB300 / Vera Rubin\nPUE 1,10" if es else "IT node 1–64 MW\nGB300 / Vera Rubin\nPUE 1.10", "#d9f0d3")
    box(47, 35, 17, 11, "CDU e intercambiador\ncerrado, 45–55 °C" if es else "CDU and closed\nheat exchanger, 45–55 °C", "#fde0c5")
    box(76, 39, 22, 9, "1  Camarones RAS 29 °C" if es else "1  Camarón RAS 29 °C", "#cde3f6")
    box(76, 25, 22, 9, "2  Secado: café, fruta, harinas\ny piensos; bomba de calor" if es else "2  Drying: coffee, fruit, meals\nand feed; heat pump", "#f6e8a8")
    box(76, 11, 22, 9, "3  Enfriador seco\n(sin agua del río)" if es else "3  Dry cooler\n(no river water)", "#e5e5e5")
    box(23, 4, 17, 11, "Fibra oscura DWDM\n51,2 Tb/s; ≤2,2 ms" if es else "DWDM dark fibre\n51.2 Tb/s; ≤2.2 ms", "#e8dff5")
    box(47, 4, 17, 11, "Pargo mancha\n(golfo de Nicoya)" if es else "Spotted rose snapper\n(Gulf of Nicoya)", "#d6eadf")
    arrow(16.5, 40.5, 22.5, 40.5, "#1d6399"); ax.text(19.5, 33.0, "MT\ninterrumpible" if es else "MV\ninterruptible", ha="center", fontsize=5.6, color="#1d6399")
    arrow(40.5, 40.5, 46.5, 40.5, "#b0413e"); ax.text(43.5, 33.0, "85 %\ndel calor" if es else "85%\nof heat", ha="center", fontsize=5.6, color="#b0413e")
    arrow(64.5, 43, 75.5, 43.5, "#b0413e"); arrow(64.5, 40, 75.5, 29.5, "#b0413e"); arrow(64.5, 37, 75.5, 15.5, "#888")
    arrow(31.5, 34.5, 31.5, 15.5, "#6a51a3")
    arrow(75.5, 41, 64.5, 13, "#2b7bb9"); arrow(64.5, 8, 75.5, 27, "#3a7d44")
    ax.text(55.5, 18.5, "harinas cruzadas" if es else "cross-species meals", ha="center", fontsize=5.6, color="#3a7d44")
    ax.text(87, 22.3, "agua destilada → venta, RAS, riego" if es else "distilled water → retail, RAS, irrigation", ha="center", fontsize=5.4, color="#2b7bb9")
    ax.text(1, 0.3, ("Prioridad: 1 camarones (demanda continua), 2 secado, 3 rechazo al aire. Sin contacto entre el agua de los servidores, el río, los alimentos y los tanques."
                     if es else "Priority: 1 camarones (continuous demand), 2 drying, 3 rejection to air. No contact between server water, river, food and tanks."), fontsize=6.0)
    fig.savefig(d / ("Fig13_esquema_nodo.png" if es else "Fig13_node_schematic.png"), bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    for L in ("es", "en"):
        fig_schematic(L, OUT / f"figuras_{L}")
