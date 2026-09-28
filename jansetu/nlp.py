"""Language, sector, and severity for a citizen text.

The core engine is a lexicon. It is inspectable, it runs without sending the
text to a model vendor, and it says when it is unsure.
"""

import re

from jansetu.catalog import DISTRICTS, HINGLISH, KEYWORDS, LANGUAGES, SECTORS, URGENT

HINGLISH_MARKERS = [
    "pani", "paani", "peyjal", "sadak", "bijli", "aspatal", "dawai",
    "kaksha", "shauchalaya", "nali", "makaan", "chhat", "gaon", "nahi", "rasta",
]
MARATHI_MARKERS = [" आहे", "पाणी", "येत नाही", "गावात", "रस्ता", "शाळ", "हातपंप"]

_RANGES = [
    ("or", 0x0B00, 0x0B7F),
    ("pa", 0x0A00, 0x0A7F),
    ("gu", 0x0A80, 0x0AFF),
    ("ta", 0x0B80, 0x0BFF),
    ("te", 0x0C00, 0x0C7F),
    ("kn", 0x0C80, 0x0CFF),
    ("ml", 0x0D00, 0x0D7F),
    ("bn", 0x0980, 0x09FF),
    ("deva", 0x0900, 0x097F),
]


def _script_counts(text: str) -> dict:
    counts = {code: 0 for code, _, _ in _RANGES}
    latin = 0
    for ch in text:
        o = ord(ch)
        if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            latin += 1
            continue
        for code, start, end in _RANGES:
            if start <= o <= end:
                counts[code] += 1
                break
    counts["latin"] = latin
    return counts


def _hits(text: str, keywords: list[str]) -> list[str]:
    found = []
    for kw in keywords:
        if kw.isascii():
            if re.search(rf"\b{re.escape(kw)}\b", text, flags=re.IGNORECASE):
                found.append(kw)
        elif kw in text:
            found.append(kw)
    return found


def _sector_scores(text: str, table: dict) -> dict:
    scores = {}
    matched = {}
    for sector, words in table.items():
        got = _hits(text, words)
        if got:
            scores[sector] = len(got)
            matched[sector] = got
    return scores, matched


def _pick_sector(scores: dict) -> tuple[str, float]:
    if not scores:
        return "general", 0.0
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_sector, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    if second == top:
        return "general", 0.34
    confidence = top / (top + second) if second else min(0.92, 0.62 + 0.1 * top)
    return top_sector, round(confidence, 2)


def _severity(text: str, sector: str) -> int:
    if sector == "general":
        return 1
    level = 3
    if any(mark in text.lower() if mark.isascii() else mark in text for mark in URGENT):
        level += 1
    if re.search(r"\b([7-9]|[12]\d)\b", text):
        level += 1
    return min(5, level)


def _mentioned_district(text: str):
    folded = text.casefold()
    best = None
    best_len = 0
    for district in DISTRICTS:
        names = [district["name"], *district.get("aliases", [])]
        for name in names:
            if name.isascii():
                hit = name.casefold() in folded
            else:
                hit = name in text
            if hit and len(name) > best_len:
                best = district["name"]
                best_len = len(name)
    return best


def classify(text: str) -> dict:
    raw = (text or "").strip()
    counts = _script_counts(raw)
    indic = {k: v for k, v in counts.items() if k not in {"latin"} and v}
    dominant = max(indic, key=indic.get) if indic else "latin"

    if dominant == "bn" and ("ৰ" in raw or "ৱ" in raw):
        language = "as"
        scores, matched = _sector_scores(raw, KEYWORDS["as"])
    elif dominant == "deva":
        mr_scores, mr_matched = _sector_scores(raw, KEYWORDS["mr"])
        hi_scores, hi_matched = _sector_scores(raw, KEYWORDS["hi"])
        mr_total = sum(mr_scores.values())
        hi_total = sum(hi_scores.values())
        marathi_marker = any(mark in raw for mark in MARATHI_MARKERS)
        if mr_total > hi_total or (marathi_marker and mr_total >= hi_total and mr_total):
            language = "mr"
            scores, matched = mr_scores, mr_matched
        else:
            language = "hi"
            scores, matched = hi_scores, hi_matched
    elif dominant == "latin":
        en_scores, en_matched = _sector_scores(raw, KEYWORDS["en"])
        hi_scores, hi_matched = _sector_scores(raw, HINGLISH)
        marker = any(re.search(rf"\b{re.escape(w)}\b", raw, flags=re.IGNORECASE) for w in HINGLISH_MARKERS)
        if marker and sum(hi_scores.values()) >= sum(en_scores.values()) and hi_scores:
            language = "hi"
            scores, matched = hi_scores, hi_matched
        else:
            language = "en"
            # English wins; hinglish synonyms still count toward the same sector.
            scores = dict(en_scores)
            matched = {k: list(v) for k, v in en_matched.items()}
            for sector, words in hi_matched.items():
                scores[sector] = scores.get(sector, 0) + len(words)
                matched.setdefault(sector, []).extend(words)
    else:
        language = dominant
        scores, matched = _sector_scores(raw, KEYWORDS.get(language, {}))

    sector, confidence = _pick_sector(scores)
    signals = matched.get(sector, []) if sector != "general" else []
    severity = _severity(raw, sector)
    lang_meta = LANGUAGES.get(language, LANGUAGES["en"])
    sector_meta = SECTORS.get(sector)
    if sector == "general":
        gloss = f"{lang_meta['label']}. No clear sector yet. Ask which need this is."
        sector_label = "Unclear"
        sector_label_hi = "अस्पष्ट"
    else:
        gloss = (
            f"{lang_meta['label']}. {sector_meta['label']}. "
            f"Severity {severity} of 5. "
            f"Words that decided it: {', '.join(signals[:4]) or 'the keypad'}."
        )
        sector_label = sector_meta["label"]
        sector_label_hi = sector_meta["label_hi"]

    return {
        "language": language,
        "language_label": lang_meta["label"],
        "language_native": lang_meta["native"],
        "sector": sector,
        "sector_label": sector_label,
        "sector_label_hi": sector_label_hi,
        "confidence": confidence,
        "severity": severity,
        "signals": signals[:6],
        "gloss": gloss,
        "district": _mentioned_district(raw),
        "speech": lang_meta["speech"],
    }


def reply_for(language: str, kind: str, **values) -> str:
    from jansetu.catalog import REPLIES

    pack = REPLIES.get(language) or REPLIES["en"]
    template = pack.get(kind) or REPLIES["en"][kind]
    return template.format(**values)
