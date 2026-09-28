"""Optional cabinet-note prose.

Off unless GEMINI_API_KEY or GOOGLE_API_KEY is set. The payload is the
published numbers, never the raw citizen text.
"""

import json
import os
import urllib.request


def narrate(cell: dict) -> str | None:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    brief = {
        "district": cell["district"],
        "state": cell["state"],
        "sector": cell["sector_label"],
        "scheme": cell["scheme"],
        "project": cell["project"],
        "priority": cell["priority"],
        "signal": cell["signal"],
        "requests": cell["requests"],
        "coverage_index": cell["infra"],
        "rural_percent": cell["rural"],
        "deprivation": cell["deprivation"],
        "allocated_crore": cell["allocated_cr"],
        "spent_crore": cell["spent_cr"],
        "indicative_package_crore": cell["tranche_cr"],
        "beneficiaries": cell["beneficiary_label"],
        "language": cell["top_language"],
    }
    prompt = (
        "Write a 110-word note for an Indian planning desk. Use only these figures. "
        "Do not invent statistics, scheme rules, or quotations. Short sentences. "
        "No bullet points. End with this exact sentence: "
        "This is a decision aid, not a sanction.\n"
        + json.dumps(brief, ensure_ascii=False)
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    payload = json.dumps(
        {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 280}}
    ).encode()
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None
