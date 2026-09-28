"""Turn the ledger into hotspots, an under-heard shelf, and cabinet notes.

Score, out of 100:

    34  demand per lakh residents, weighted by severity, recency, and status
    30  infrastructure deficit (100 minus the coverage index)
    20  equity: rural share and deprivation
    16  allocation gap: share of voice minus share of the scheme line

Demand is what people managed to say. The under-heard shelf is separate on
purpose: a 3× inflation of sparse complaints would invent precision the
records do not have.
"""

from datetime import datetime, timedelta, timezone

from jansetu.catalog import LANGUAGES, SECTORS, STATE_ATLAS, WEIGHTS

IST = timezone(timedelta(hours=5, minutes=30))
STATUS_WEIGHT = {"open": 1.0, "acknowledged": 0.85, "in_plan": 0.45, "addressed": 0.12}


def people(n: float) -> str:
    n = int(round(n))
    if n >= 10_000_000:
        return f"{n / 10_000_000:.2f} crore"
    if n >= 100_000:
        return f"{n / 100_000:.2f} lakh"
    return f"{n:,}"


def crore(n: float) -> str:
    return f"{n:.1f}"


def _parse_time(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt


def _recency(created: str, now: datetime) -> float:
    days = max(0, (now - _parse_time(created)).days)
    if days <= 21:
        return 1.0
    if days <= 60:
        return 0.75
    if days <= 110:
        return 0.5
    return 0.35


def _norm(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _package(pop, rural, deficit, sector):
    meta = SECTORS[sector]
    gap_people = pop * (rural / 100) * deficit * meta["slice"]
    units = gap_people / meta["people_per_unit"] if meta["people_per_unit"] else 0
    rupees = units * meta["rupees"]
    return max(0, gap_people), max(0, units), rupees / 1e7


def _narrative(cell, peers):
    peer_txt = ""
    if peers:
        names = ", ".join(peers[:3])
        peer_txt = f" Other {cell['sector_label'].lower()} hotspots on this ledger: {names}."
    quiet = ""
    if cell["signal"] == "Under-heard":
        quiet = (
            " Complaint volume is thin. Voice reach in this district is low, "
            "so a quiet ledger is not evidence that the need is met."
        )
    en = (
        f"{cell['district']} has {cell['requests']} citizen records on {cell['sector_label'].lower()}, "
        f"mostly in {cell['top_language']}. The coverage index is {cell['infra']} out of 100. "
        f"The district is {cell['rural']:.0f}% rural, with a deprivation index of {cell['deprivation']:.0f}. "
        f"The {cell['scheme']} line this year is ₹{crore(cell['allocated_cr'])} crore, "
        f"of which ₹{crore(cell['spent_cr'])} crore is spent. "
        f"The indicative first-year package is ₹{crore(cell['tranche_cr'])} crore "
        f"for about {people(cell['units'])} {cell['unit_label']}, "
        f"reaching about {cell['beneficiary_label']} people."
        f"{quiet}{peer_txt} "
        f"This note is a decision aid. It does not sanction expenditure."
    )
    hi = (
        f"{cell['district']} में {cell['sector_label_hi']} की {cell['requests']} नागरिक शिकायतें हैं, "
        f"अधिकतर {cell['top_language_native']} में। कवरेज अंक {cell['infra']} / 100 है। "
        f"जिला {cell['rural']:.0f}% ग्रामीण है और वंचना अंक {cell['deprivation']:.0f} है। "
        f"{cell['scheme']} में इस वर्ष ₹{crore(cell['allocated_cr'])} करोड़ का प्रावधान है, "
        f"जिसमें से ₹{crore(cell['spent_cr'])} करोड़ खर्च हुए हैं। "
        f"पहले वर्ष का संकेतक पैकेज ₹{crore(cell['tranche_cr'])} करोड़ है, "
        f"लगभग {cell['beneficiary_label']} लोगों के लिए। "
        f"यह नोट फैसला आसान करता है। यह मंजूरी नहीं है।"
    )
    return en, hi


def load(conn):
    districts = [dict(row) for row in conn.execute("SELECT * FROM districts ORDER BY name")]
    for district in districts:
        import json

        district["infra"] = json.loads(district["infra_json"])
    investments = {}
    for row in conn.execute("SELECT * FROM investments"):
        investments[(row["district_id"], row["sector"])] = dict(row)
    requests = [dict(row) for row in conn.execute("SELECT * FROM requests")]
    return districts, investments, requests


def score(conn, extra=None):
    districts, investments, requests = load(conn)
    if extra:
        requests = requests + [extra]
    now = datetime.now(IST)
    by_key = {}
    for district in districts:
        for sector in SECTORS:
            by_key[(district["id"], sector)] = []
    for req in requests:
        if req["sector"] not in SECTORS:
            continue
        by_key.setdefault((req["district_id"], req["sector"]), []).append(req)

    raw_cells = []
    for district in districts:
        equity = 0.6 * (district["rural"] / 100) + 0.4 * (district["deprivation"] / 100)
        for sector, meta in SECTORS.items():
            reqs = by_key.get((district["id"], sector), [])
            demand = 0.0
            for req in reqs:
                demand += (req["severity"] / 3) * _recency(req["created_at"], now) * STATUS_WEIGHT.get(req["status"], 1)
            per_lakh = demand / (district["pop"] / 1e5)
            infra = district["infra"][sector]
            deficit = (100 - infra) / 100
            money = investments.get((district["id"], sector), {})
            allocated = float(money.get("allocated_cr") or 0)
            spent = float(money.get("spent_cr") or 0)
            raw_cells.append(
                {
                    "district_id": district["id"],
                    "district": district["name"],
                    "slug": district["slug"],
                    "state": district["state"],
                    "lang": district["lang"],
                    "sector": sector,
                    "reqs": reqs,
                    "demand": demand,
                    "per_lakh": per_lakh,
                    "infra": infra,
                    "deficit": deficit,
                    "equity": equity,
                    "allocated_cr": allocated,
                    "spent_cr": spent,
                    "pop": district["pop"],
                    "rural": district["rural"],
                    "literacy": district["literacy"],
                    "deprivation": district["deprivation"],
                    "voice": district["voice"],
                }
            )

    for sector in SECTORS:
        group = [c for c in raw_cells if c["sector"] == sector]
        demand_total = sum(c["per_lakh"] for c in group) or 1
        alloc_total = sum(c["allocated_cr"] for c in group) or 1
        for cell in group:
            cell["gap_raw"] = max(0.0, (cell["per_lakh"] / demand_total) - (cell["allocated_cr"] / alloc_total))

    absolute_n = _norm([c["demand"] for c in raw_cells])
    intensity_n = _norm([c["per_lakh"] for c in raw_cells])
    gap_n = _norm([c["gap_raw"] for c in raw_cells])
    for cell, absolute, intensity, gap in zip(raw_cells, absolute_n, intensity_n, gap_n):
        # Large districts must not disappear behind a per-lakh rate, and a small
        # district must not win on a handful of messages alone.
        cell["demand_n"] = round(0.55 * absolute + 0.45 * intensity, 4)
        priority = 100 * (
            WEIGHTS["demand"] * cell["demand_n"]
            + WEIGHTS["need"] * cell["deficit"]
            + WEIGHTS["equity"] * cell["equity"]
            + WEIGHTS["money"] * gap
        )
        cell["priority"] = round(priority)

    ordered = sorted(raw_cells, key=lambda c: c["priority"], reverse=True)
    for rank, cell in enumerate(ordered):
        if rank < 12 and cell["demand_n"] >= 0.28 and len(cell["reqs"]) >= 5:
            cell["signal"] = "Hotspot"
        elif rank < 40:
            cell["signal"] = "Priority"
        else:
            cell["signal"] = "Watch"

    cells = [_public_cell(c) for c in raw_cells]
    by_sector_state = {}
    for cell in cells:
        by_sector_state.setdefault(cell["sector"], []).append(cell)

    for cell in cells:
        peers = [
            other["district"]
            for other in by_sector_state[cell["sector"]]
            if other["signal"] == "Hotspot" and other["slug"] != cell["slug"]
        ]
        peers.sort()
        en, hi = _narrative(cell, peers)
        cell["narrative_en"] = en
        cell["narrative_hi"] = hi
        cell["peers"] = peers[:4]

    under = []
    for cell in cells:
        if cell["deficit"] >= 0.55 and cell["voice"] <= 0.32 and cell["requests"] <= 5:
            under.append(cell)
    under.sort(key=lambda c: (c["deficit"] * (0.55 + c["equity"]) * (1.15 - c["voice"])), reverse=True)
    diverse = []
    seen_districts = set()
    for cell in under:
        if cell["district"] in seen_districts:
            continue
        diverse.append(cell)
        seen_districts.add(cell["district"])
    under = diverse[:3]
    for cell in under:
        cell["signal"] = "Under-heard"
        peers = [p for p in cell["peers"]]
        en, hi = _narrative(cell, peers)
        cell["narrative_en"] = en
        cell["narrative_hi"] = hi

    briefs = _pick_briefs(cells, under[:1])
    hotspots = [c for c in cells if c["signal"] == "Hotspot"]
    unfunded = sum(max(0, c["tranche_cr"] - c["allocated_cr"]) for c in briefs)
    people_named = sum(c["beneficiaries"] for c in briefs)

    states = _states(cells)
    languages = _languages(requests)
    sectors = _sectors(cells, requests)
    open_count = sum(1 for r in requests if r["status"] == "open")
    heard_90 = 0
    for req in requests:
        if (now - _parse_time(req["created_at"])).days <= 90:
            heard_90 += 1

    pulse = {
        "requests": len(requests),
        "open": open_count,
        "languages": sum(1 for row in languages if row["count"]),
        "districts": len(districts),
        "states": len({d["state"] for d in districts}),
        "hotspots": len(hotspots),
        "underheard": len(under),
        "unfunded_cr": round(unfunded, 1),
        "people_named": int(people_named),
        "people_label": people(people_named),
        "heard_90": heard_90,
    }
    ranked = sorted(cells, key=lambda c: c["priority"], reverse=True)
    return {
        "pulse": pulse,
        "states": states,
        "cells": ranked,
        "briefs": briefs,
        "underheard": under[:4],
        "languages": languages,
        "sectors": sectors,
        "generated_at": now.isoformat(timespec="minutes"),
    }


def _public_cell(cell):
    meta = SECTORS[cell["sector"]]
    beneficiaries, units, tranche = _package(cell["pop"], cell["rural"], cell["deficit"], cell["sector"])
    langs = {}
    for req in cell["reqs"]:
        langs[req["language"]] = langs.get(req["language"], 0) + 1
    top_lang = max(langs, key=langs.get) if langs else cell["lang"]
    lang_meta = LANGUAGES.get(top_lang, LANGUAGES["en"])
    quotes = sorted(cell["reqs"], key=lambda r: (r["severity"], r["created_at"]), reverse=True)[:3]
    return {
        "district": cell["district"],
        "slug": cell["slug"],
        "state": cell["state"],
        "sector": cell["sector"],
        "sector_label": meta["label"],
        "sector_label_hi": meta["label_hi"],
        "scheme": meta["scheme"],
        "project": meta["project"],
        "project_hi": meta["project_hi"],
        "requests": len(cell["reqs"]),
        "open": sum(1 for r in cell["reqs"] if r["status"] == "open"),
        "severity": round(sum(r["severity"] for r in cell["reqs"]) / len(cell["reqs"]), 1) if cell["reqs"] else 0,
        "infra": cell["infra"],
        "deficit": round(cell["deficit"], 2),
        "demand_n": round(cell["demand_n"], 2),
        "equity": round(cell["equity"], 2),
        "allocated_cr": cell["allocated_cr"],
        "spent_cr": cell["spent_cr"],
        "tranche_cr": round(tranche, 1),
        "gap_cr": round(max(0, tranche - cell["allocated_cr"]), 1),
        "beneficiaries": int(beneficiaries),
        "beneficiary_label": people(beneficiaries),
        "units": int(round(units)),
        "unit_label": meta["unit"],
        "priority": cell["priority"],
        "signal": cell["signal"],
        "top_language": lang_meta["label"],
        "top_language_native": lang_meta["native"],
        "voice": cell["voice"],
        "rural": cell["rural"],
        "literacy": cell["literacy"],
        "deprivation": cell["deprivation"],
        "pop": cell["pop"],
        "pop_label": people(cell["pop"]),
        "quotes": [
            {
                "text": q["body"],
                "language": q["language"],
                "channel": q["channel"],
                "severity": q["severity"],
                "ref": q["ref"],
            }
            for q in quotes
        ],
    }


def _pick_briefs(cells, forced):
    picked = []
    used_sectors = set()
    used_states = set()
    ordered = sorted(cells, key=lambda c: c["priority"], reverse=True)
    for cell in ordered:
        if cell["signal"] not in {"Hotspot", "Priority"}:
            continue
        if cell["sector"] in used_sectors or cell["state"] in used_states:
            continue
        picked.append(cell)
        used_sectors.add(cell["sector"])
        used_states.add(cell["state"])
        if len(picked) == 5:
            break
    if len(picked) < 5:
        for cell in ordered:
            if cell in picked or cell["sector"] in used_sectors:
                continue
            picked.append(cell)
            used_sectors.add(cell["sector"])
            if len(picked) == 5:
                break
    for cell in forced:
        if cell not in picked:
            picked.append(cell)
    return picked


def _states(cells):
    grouped = {}
    for cell in cells:
        bucket = grouped.setdefault(
            cell["state"],
            {"state": cell["state"], "priority": 0, "requests": 0, "top": None, "x": 50, "y": 50},
        )
        bucket["requests"] += cell["requests"]
        if cell["priority"] >= bucket["priority"]:
            bucket["priority"] = cell["priority"]
            bucket["top"] = cell
        pos = STATE_ATLAS.get(cell["state"])
        if pos:
            bucket["x"], bucket["y"] = pos
    rows = []
    for bucket in grouped.values():
        top = bucket["top"]
        rows.append(
            {
                "state": bucket["state"],
                "x": bucket["x"],
                "y": bucket["y"],
                "priority": bucket["priority"],
                "requests": bucket["requests"],
                "sector": top["sector"] if top else "",
                "sector_label": top["sector_label"] if top else "",
                "district": top["district"] if top else "",
                "signal": top["signal"] if top else "Watch",
            }
        )
    rows.sort(key=lambda r: r["priority"], reverse=True)
    return rows


def _languages(requests):
    counts = {code: 0 for code in LANGUAGES}
    for req in requests:
        if req["language"] in counts:
            counts[req["language"]] += 1
    rows = [
        {"code": code, "label": meta["label"], "native": meta["native"], "count": counts[code]}
        for code, meta in LANGUAGES.items()
    ]
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


def _sectors(cells, requests):
    counts = {code: 0 for code in SECTORS}
    for req in requests:
        if req["sector"] in counts:
            counts[req["sector"]] += 1
    rows = []
    for code, meta in SECTORS.items():
        gap = sum(c["gap_cr"] for c in cells if c["sector"] == code and c["signal"] in {"Hotspot", "Priority"})
        rows.append({"code": code, "label": meta["label"], "label_hi": meta["label_hi"], "count": counts[code], "gap_cr": round(gap, 1)})
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


def find_cell(board, slug, sector):
    for cell in board["cells"]:
        if cell["slug"] == slug and cell["sector"] == sector:
            return cell
    for cell in board["underheard"]:
        if cell["slug"] == slug and cell["sector"] == sector:
            return cell
    return None


def home_view(board):
    quotes = []
    seen = set()
    ranked = sorted(board["cells"], key=lambda c: (c["severity"], c["requests"]), reverse=True)
    for cell in ranked:
        for quote in cell["quotes"]:
            if quote["text"] in seen:
                continue
            seen.add(quote["text"])
            quotes.append(
                {
                    "text": quote["text"],
                    "language": quote["language"],
                    "channel": quote["channel"],
                    "district": cell["district"],
                    "state": cell["state"],
                    "sector_label": cell["sector_label"],
                    "severity": quote["severity"],
                }
            )
            if len(quotes) == 4:
                break
        if len(quotes) == 4:
            break
    money_rows = []
    for cell in board["briefs"][:5]:
        money_rows.append(
            {
                "name": f"{cell['district']} · {cell['sector_label']}",
                "tranche_cr": cell["tranche_cr"],
                "allocated_cr": cell["allocated_cr"],
            }
        )
    return {
        "pulse": board["pulse"],
        "quotes": quotes,
        "money": money_rows,
        "languages": board["languages"],
        "briefs": [
            {
                "district": b["district"],
                "state": b["state"],
                "sector_label": b["sector_label"],
                "priority": b["priority"],
                "signal": b["signal"],
                "slug": b["slug"],
                "sector": b["sector"],
            }
            for b in board["briefs"]
        ],
    }
