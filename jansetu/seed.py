import random
import re
from datetime import datetime, timedelta, timezone

from jansetu.catalog import CHANNELS, DISTRICTS, SECTORS
from jansetu.nlp import classify
from jansetu.phrases import render

IST = timezone(timedelta(hours=5, minutes=30))
FY = "2026-27"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")


def allocation_cr(pop: int, infra: int) -> float:
    """Money follows places that are already better served. That bias is the point."""
    coverage = infra / 100
    raw = (pop / 1e5) * 0.36 * (coverage ** 1.5)
    return round(max(0.8, raw), 1)


def seed(conn):
    rng = random.Random(2026)
    now = datetime.now(IST).replace(microsecond=0)
    failures = []
    serial = 0

    for district in DISTRICTS:
        cur = conn.execute(
            """
            INSERT INTO districts
                (name, slug, state, lang, pop, rural, literacy, deprivation, voice, infra_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                district["name"],
                slugify(district["name"]),
                district["state"],
                district["lang"],
                district["pop"],
                district["rural"],
                district["literacy"],
                district["deprivation"],
                district["voice"],
                __import__("json").dumps(district["infra"]),
            ),
        )
        district_id = cur.lastrowid
        for sector, meta in SECTORS.items():
            infra = district["infra"][sector]
            allocated = allocation_cr(district["pop"], infra)
            spent = round(allocated * rng.uniform(0.38, 0.9), 1)
            conn.execute(
                """
                INSERT INTO investments (district_id, sector, scheme, allocated_cr, spent_cr, fy)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (district_id, sector, meta["scheme"], allocated, spent, FY),
            )
            deficit = (100 - infra) / 100
            expected = (deficit ** 1.55) * district["voice"] * (district["pop"] / 2.6e5) * 6.2
            count = int(max(0, min(16, round(expected))))
            for index in range(count):
                if rng.random() < 0.8:
                    lang = district["lang"]
                else:
                    lang = rng.choice(["hi", "en"])
                number = rng.randint(3, 22)
                body = render(lang, sector, index, number)
                reading = classify(body)
                if reading["language"] != lang or reading["sector"] != sector:
                    failures.append(
                        f"{lang}/{sector} -> {reading['language']}/{reading['sector']} :: {body}"
                    )
                    continue
                roll = rng.random()
                channel = rng.choices(
                    ["whatsapp", "voice", "web", "ivr", "sms"],
                    weights=[38, 22, 18, 12, 10],
                )[0]
                days_ago = rng.randint(0, 110)
                if days_ago < 18:
                    status = "open" if roll < 0.84 else "acknowledged"
                elif roll < 0.52:
                    status = "open"
                elif roll < 0.74:
                    status = "acknowledged"
                elif roll < 0.9:
                    status = "in_plan"
                else:
                    status = "addressed"
                created = now - timedelta(days=days_ago, hours=rng.randint(0, 20), minutes=rng.randint(0, 59))
                serial += 1
                ref = f"JS-26-{serial:05d}"
                conn.execute(
                    """
                    INSERT INTO requests (
                        ref, district_id, channel, language, sector, severity, confidence,
                        body, gloss, signals, status, phone_last4, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                    """,
                    (
                        ref,
                        district_id,
                        channel,
                        lang,
                        sector,
                        reading["severity"],
                        reading["confidence"],
                        body,
                        reading["gloss"],
                        ",".join(reading["signals"]),
                        status,
                        created.isoformat(timespec="minutes"),
                    ),
                )

    if failures:
        preview = "\n".join(failures[:12])
        raise RuntimeError(f"{len(failures)} phrases failed classification:\n{preview}")


# Channel names are part of the public intake contract.
assert set(CHANNELS) >= {"web", "voice", "whatsapp", "sms", "ivr"}
