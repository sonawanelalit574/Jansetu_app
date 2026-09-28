import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template, request

from jansetu.catalog import CHANNELS, LANGUAGES, SECTORS
from jansetu.db import connect
from jansetu.gemini import narrate
from jansetu.nlp import classify, reply_for
from jansetu.phrases import PHRASES
from jansetu.scoring import find_cell, home_view, score

IST = timezone(timedelta(hours=5, minutes=30))
bp = Blueprint("jansetu", __name__)


def _districts(conn):
    rows = conn.execute(
        "SELECT id, name, slug, state, lang FROM districts ORDER BY state, name"
    ).fetchall()
    return [dict(row) for row in rows]


def _samples(conn):
    by_lang = {}
    for row in _districts(conn):
        by_lang.setdefault(row["lang"], row)
    samples = []
    for code, meta in LANGUAGES.items():
        if code == "en":
            district = by_lang.get("hi")
            sector = "water"
        else:
            district = by_lang.get(code)
            sector = "water"
        if not district:
            continue
        template = PHRASES[code][sector][0]
        text = template.format(n=8) if "{n}" in template else template
        samples.append(
            {
                "lang": code,
                "label": meta["native"],
                "sector": sector,
                "district_id": district["id"],
                "district": district["name"],
                "text": text,
            }
        )
    return samples


def _clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", (value or "")).strip()
    return text[:800]


def _last4(phone: str):
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 10:
        return None
    return digits[-4:]


def _effect(before, after, reading):
    if after is None:
        return "Recorded on the ledger."
    if after["requests"] <= 3 and after["deficit"] >= 0.5:
        return (
            f"Few people from {after['district']} have been heard on {after['sector_label'].lower()}. "
            "This record is evidence the desk did not otherwise have."
        )
    if after["signal"] == "Hotspot":
        return (
            f"This joins a hotspot the desk can already see. "
            f"{after['district']} · {after['sector_label']} is at priority {after['priority']}."
        )
    return (
        f"{after['district']} · {after['sector_label']} moves from {before['priority'] if before else 0} "
        f"to {after['priority']} on the national score."
    )


@bp.get("/")
def landing():
    conn = connect()
    board = score(conn)
    conn.close()
    return render_template("landing.html", home=home_view(board))


@bp.get("/desk")
def desk():
    conn = connect()
    districts = _districts(conn)
    samples = _samples(conn)
    recent = conn.execute(
        """
        SELECT r.ref, r.body, r.language, r.channel, r.sector, r.created_at, d.name AS district, d.state
        FROM requests r JOIN districts d ON d.id = r.district_id
        ORDER BY r.created_at DESC LIMIT 6
        """
    ).fetchall()
    conn.close()
    ivr = {}
    for code, sector_lines in PHRASES.items():
        ivr[code] = {}
        for sector, options in sector_lines.items():
            line = options[0]
            ivr[code][sector] = line.format(n=6) if "{n}" in line else line
    return render_template(
        "desk.html",
        districts=districts,
        samples=samples,
        recent=[dict(row) for row in recent],
        languages=LANGUAGES,
        sectors=SECTORS,
        ivr=ivr,
    )


@bp.get("/console")
def console():
    return render_template("console.html", sectors=SECTORS)


@bp.get("/method")
def method():
    return render_template("method.html", weights={
        "demand": 34, "need": 30, "equity": 20, "money": 16,
    })


@bp.get("/deck")
def deck():
    conn = connect()
    board = score(conn)
    conn.close()
    return render_template("deck.html", home=home_view(board), brief=board["briefs"][0], under=board["underheard"][:1])


@bp.get("/r/<ref>")
def track(ref):
    conn = connect()
    row = conn.execute(
        """
        SELECT r.*, d.name AS district, d.state, d.slug
        FROM requests r JOIN districts d ON d.id = r.district_id
        WHERE r.ref = ?
        """,
        (ref.strip().upper(),),
    ).fetchone()
    conn.close()
    if row is None:
        return render_template("track.html", item=None, ref=ref), 404
    item = dict(row)
    item["sector_label"] = SECTORS.get(item["sector"], {}).get("label", item["sector"])
    item["language_label"] = LANGUAGES.get(item["language"], {}).get("label", item["language"])
    item["channel_label"] = CHANNELS.get(item["channel"], item["channel"])
    return render_template("track.html", item=item, ref=item["ref"])


@bp.get("/note/<slug>/<sector>")
def note(slug, sector):
    if sector not in SECTORS:
        return render_template("note.html", cell=None), 404
    conn = connect()
    board = score(conn)
    conn.close()
    cell = find_cell(board, slug, sector)
    if cell is None:
        return render_template("note.html", cell=None), 404
    return render_template("note.html", cell=cell)


@bp.post("/api/analyze")
def analyze():
    payload = request.get_json(silent=True) or {}
    text = _clean_text(payload.get("text", ""))
    if len(text) < 2:
        return jsonify({"ok": False, "error": "Write a little more."}), 400
    reading = classify(text)
    conn = connect()
    districts = _districts(conn)
    mentioned = None
    if reading["district"]:
        mentioned = next((d for d in districts if d["name"] == reading["district"]), None)
    district_id = payload.get("district_id") or (mentioned["id"] if mentioned else None)
    cell = None
    if district_id and reading["sector"] in SECTORS:
        board = score(conn)
        district = next((d for d in districts if d["id"] == int(district_id)), None)
        if district:
            cell = find_cell(board, district["slug"], reading["sector"])
    conn.close()
    reply_lang = reading["language"] if reading["language"] in LANGUAGES else "en"
    needs = []
    if reading["sector"] == "general":
        needs.append("sector")
    if not district_id:
        needs.append("district")
    reply = None
    if "sector" in needs:
        reply = reply_for(reply_lang, "ask_sector")
    elif "district" in needs:
        reply = reply_for(reply_lang, "ask_district")
    return jsonify(
        {
            "ok": True,
            "reading": reading,
            "needs": needs,
            "reply": reply,
            "district_id": district_id,
            "preview": None
            if cell is None
            else {
                "district": cell["district"],
                "sector_label": cell["sector_label"],
                "priority": cell["priority"],
                "signal": cell["signal"],
                "requests": cell["requests"],
            },
        }
    )


@bp.post("/api/requests")
def file_request():
    payload = request.get_json(silent=True) or {}
    text = _clean_text(payload.get("text", ""))
    channel = payload.get("channel") or "web"
    if channel not in CHANNELS:
        return jsonify({"ok": False, "error": "Unknown channel."}), 400
    if len(text) < 8:
        return jsonify({"ok": False, "error": "Say a little more about the need and the place."}), 400
    try:
        district_id = int(payload.get("district_id") or 0)
    except (TypeError, ValueError):
        district_id = 0
    reading = classify(text)
    sector = payload.get("sector") if payload.get("sector") in SECTORS else reading["sector"]
    if channel == "ivr" and payload.get("sector") in SECTORS:
        sector = payload["sector"]
    language = reading["language"]
    if sector == "general":
        return jsonify(
            {
                "ok": False,
                "needs": ["sector"],
                "reading": reading,
                "reply": reply_for(language if language in LANGUAGES else "en", "ask_sector"),
            }
        )
    conn = connect()
    district = conn.execute("SELECT * FROM districts WHERE id = ?", (district_id,)).fetchone()
    if district is None:
        mentioned = reading["district"]
        if mentioned:
            district = conn.execute("SELECT * FROM districts WHERE name = ?", (mentioned,)).fetchone()
    if district is None:
        conn.close()
        return jsonify(
            {
                "ok": False,
                "needs": ["district"],
                "reading": reading,
                "reply": reply_for(language if language in LANGUAGES else "en", "ask_district"),
            }
        )
    before_board = score(conn)
    before = find_cell(before_board, district["slug"], sector)
    ref = "JS-" + secrets.token_hex(4).upper()
    created = datetime.now(IST).replace(microsecond=0).isoformat(timespec="minutes")
    gloss = reading["gloss"]
    if sector != reading["sector"] and sector in SECTORS:
        gloss = f"{reading['language_label']}. Marked as {SECTORS[sector]['label']} from the keypad. {reading['gloss']}"
    conn.execute(
        """
        INSERT INTO requests (
            ref, district_id, channel, language, sector, severity, confidence,
            body, gloss, signals, status, phone_last4, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
        """,
        (
            ref,
            district["id"],
            channel,
            language,
            sector,
            reading["severity"] if sector == reading["sector"] else max(3, reading["severity"]),
            reading["confidence"] if sector == reading["sector"] else 0.99,
            text,
            gloss,
            ",".join(reading["signals"]),
            _last4(payload.get("phone", "")),
            created,
        ),
    )
    conn.commit()
    after_board = score(conn)
    after = find_cell(after_board, district["slug"], sector)
    conn.close()
    sector_label = SECTORS[sector]["label"]
    return jsonify(
        {
            "ok": True,
            "ref": ref,
            "reading": reading,
            "sector": sector,
            "sector_label": sector_label,
            "district": district["name"],
            "state": district["state"],
            "reply": reply_for(
                language if language in LANGUAGES else "en",
                "filed",
                ref=ref,
                district=district["name"],
                sector=sector_label,
            ),
            "effect": _effect(before, after, reading),
            "track": f"/r/{ref}",
            "note": f"/note/{district['slug']}/{sector}",
            "priority": after["priority"] if after else None,
            "signal": after["signal"] if after else None,
        }
    )


@bp.get("/api/console")
def console_api():
    state = (request.args.get("state") or "").strip()
    sector = (request.args.get("sector") or "").strip()
    q = (request.args.get("q") or "").strip().casefold()
    conn = connect()
    board = score(conn)
    conn.close()
    cells = board["cells"]
    if state:
        cells = [c for c in cells if c["state"] == state]
    if sector in SECTORS:
        cells = [c for c in cells if c["sector"] == sector]
    if q:
        cells = [c for c in cells if q in c["district"].casefold() or q in c["state"].casefold()]
    states = board["states"]
    if sector in SECTORS:
        # Atlas stays national so a sector filter still shows where that need is hottest.
        pass
    return jsonify(
        {
            "pulse": board["pulse"],
            "states": states,
            "cells": cells[:40],
            "briefs": board["briefs"],
            "underheard": board["underheard"],
            "languages": board["languages"],
            "sectors": board["sectors"],
            "generated_at": board["generated_at"],
            "filters": {"state": state, "sector": sector, "q": q},
        }
    )


@bp.get("/api/open-data")
def open_data():
    conn = connect()
    districts = [dict(row) for row in conn.execute("SELECT id, name, state, lang, pop, rural, literacy, deprivation, voice, infra_json FROM districts")]
    investments = [dict(row) for row in conn.execute("SELECT district_id, sector, scheme, allocated_cr, spent_cr, fy FROM investments")]
    requests = [
        dict(row)
        for row in conn.execute(
            """
            SELECT r.ref, d.name AS district, d.state, r.sector, r.language, r.channel,
                   r.severity, r.status, r.created_at, r.body
            FROM requests r JOIN districts d ON d.id = r.district_id
            ORDER BY r.created_at DESC
            """
        )
    ]
    conn.close()
    return jsonify(
        {
            "about": "JanSetu demonstration ledger. Not official statistics. No names and no full phone numbers.",
            "districts": districts,
            "investments": investments,
            "requests": requests,
        }
    )


@bp.post("/api/note/<slug>/<sector>/narrate")
def narrate_note(slug, sector):
    if sector not in SECTORS:
        return jsonify({"ok": False}), 404
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        return jsonify({"ok": False, "error": "No Gemini key is configured. The local note is already the record."})
    conn = connect()
    board = score(conn)
    conn.close()
    cell = find_cell(board, slug, sector)
    if cell is None:
        return jsonify({"ok": False}), 404
    text = narrate(cell)
    if not text:
        return jsonify({"ok": False, "error": "The model did not answer. The local note stands."}), 502
    return jsonify({"ok": True, "text": text})


@bp.get("/api/health")
def health():
    return jsonify({"ok": True, "name": "jansetu"})
