"""Build the JanSetu submission deck."""

import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))  # repo root, so `jansetu` package imports work
ASSETS = Path(r"C:\Users\lalit\.cursor\projects\c-Users-lalit-PycharmProjects-project-manager\assets")
OUT_DIR = ROOT / "deck_assets"
OUT_DIR.mkdir(exist_ok=True)

PAPER = RGBColor(0xF3, 0xEF, 0xE4)
INK = RGBColor(0x1C, 0x19, 0x15)
MUTED = RGBColor(0x5E, 0x58, 0x4E)
TEAL = RGBColor(0x0D, 0x6A, 0x56)
TEAL_DEEP = RGBColor(0x08, 0x48, 0x3B)
CREAM = RGBColor(0xF6, 0xF1, 0xE6)
TERRA = RGBColor(0xB8, 0x43, 0x21)
GOLD = RGBColor(0x8A, 0x6A, 0x32)
CARD = RGBColor(0xFB, 0xF7, 0xF0)
LINE = RGBColor(0xD9, 0xD0, 0xC0)
WHITE = RGBColor(0xFF, 0xFD, 0xF8)

W, H = 13.333, 7.5


def _knock_out_edges(image):
    """Clear the connected light background, leaving cream marks inside shapes."""
    image = image.convert("RGBA")
    px = image.load()
    w, h = image.size
    seen = set()
    stack = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h or (x, y) in seen:
            continue
        r, g, b, a = px[x, y]
        if a < 12 or (r > 228 and g > 216 and b > 196):
            seen.add((x, y))
            px[x, y] = (r, g, b, 0)
            stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return image


def crop_icons():
    sheet = _knock_out_edges(Image.open(ASSETS / "jansetu-icons.png"))
    w, h = sheet.size
    boxes = {
        "chat": (0, 0, w // 2, h // 2),
        "mic": (w // 2, 0, w, h // 2),
        "water": (0, h // 2, w // 2, h),
        "road": (w // 2, h // 2, w, h),
    }
    paths = {}
    for name, box in boxes.items():
        tile = sheet.crop(box)
        px = tile.load()
        tw, th = tile.size
        minx, miny, maxx, maxy = tw, th, 0, 0
        for y in range(th):
            for x in range(tw):
                if px[x, y][3] > 20:
                    minx, miny = min(minx, x), min(miny, y)
                    maxx, maxy = max(maxx, x), max(maxy, y)
        pad = 8
        tile = tile.crop(
            (
                max(0, minx - pad),
                max(0, miny - pad),
                min(tw, maxx + pad),
                min(th, maxy + pad),
            )
        )
        dest = OUT_DIR / f"{name}.png"
        tile.save(dest)
        paths[name] = dest
    logo = _knock_out_edges(Image.open(ASSETS / "jansetu-logo.png"))
    logo_dest = OUT_DIR / "logo.png"
    logo.save(logo_dest)
    paths["logo"] = logo_dest
    return paths


def _anchor(tf, anchor):
    tf._txBody.bodyPr.set("anchor", {MSO_ANCHOR.TOP: "t", MSO_ANCHOR.MIDDLE: "ctr", MSO_ANCHOR.BOTTOM: "b"}[anchor])


def text(slide, l, t, w, h, content, size=18, bold=False, color=INK, font="Calibri", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    shape = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.word_wrap = True
    _anchor(tf, anchor)
    # Allow a list of paragraphs: (text, size, bold, color)
    lines = content if isinstance(content, list) else [(content, size, bold, color)]
    for i, line in enumerate(lines):
        msg, sz, is_bold, col = line
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(0)
        run = p.add_run()
        run.text = msg
        run.font.size = Pt(sz)
        run.font.bold = is_bold
        run.font.color.rgb = col
        run.font.name = font
    return shape


def rect(slide, l, t, w, h, fill, rounded=False):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, Inches(l), Inches(t), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    if rounded:
        shape.adjustments[0] = 0.08
    # Drop the shadow python-pptx adds by default.
    sp_pr = shape._element
    effect = sp_pr.find(qn("a:effectLst"))
    # Shadow lives on spPr, not the shape element. Leave it; default is none for fill shapes.
    return shape


def blank(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = PAPER
    return slide


def footer(slide, icons, page, pages):
    rect(slide, 0, 7.22, W, 0.28, TEAL_DEEP)
    slide.shapes.add_picture(str(icons["logo"]), Inches(0.38), Inches(7.25), Inches(0.22), Inches(0.22))
    text(slide, 0.68, 7.22, 8, 0.28, "JanSetu  ·  Citizen demand, placed where public money is decided", 11, False, CREAM, anchor=MSO_ANCHOR.MIDDLE)
    text(slide, 11.4, 7.22, 1.5, 0.28, f"{page}  /  {pages}", 11, False, CREAM, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)


def kicker(slide, label):
    text(slide, 0.55, 0.32, 10, 0.32, label.upper(), 12, True, GOLD, font="Calibri")


def build():
    icons = crop_icons()
    stats = load_stats()
    pages = 10
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    prs.core_properties.title = "JanSetu"
    prs.core_properties.subject = "Citizen demand for India's infrastructure planning"
    prs.core_properties.author = "JanSetu"

    title(prs, icons)
    problem(prs, icons, 2, pages)
    product(prs, icons, 3, pages)
    channels(prs, icons, 4, pages)
    score(prs, icons, 5, pages)
    desk(prs, icons, stats, 6, pages)
    note(prs, icons, stats, 7, pages)
    quiet(prs, icons, stats, 8, pages)
    good(prs, icons, 9, pages)
    close(prs, icons)

    dest = ROOT / "JanSetu.pptx"
    prs.save(dest)
    downloads = Path.home() / "Downloads" / "JanSetu.pptx"
    downloads.write_bytes(dest.read_bytes())
    print(dest)
    print(downloads)


def load_stats():
    fallback = {
        "requests": "1,825",
        "languages": "12",
        "districts": "30",
        "hotspots": "12",
        "unfunded": "199",
        "people": "9.08 lakh",
        "lead_place": "Rayagada, Odisha",
        "lead_need": "Roads  ·  PMGSY",
        "lead_score": "75",
        "lead_pack": "19.5",
        "lead_line": "0.8",
        "quiet_place": "Malkangiri, Odisha",
        "quiet_need": "Digital connectivity  ·  BharatNet",
        "quiet_cover": "16",
        "quiet_voice": "16",
        "quiet_records": "2",
    }
    try:
        from jansetu.db import connect
        from jansetu.scoring import score

        conn = connect()
        board = score(conn)
        conn.close()
        pulse = board["pulse"]
        lead = next(c for c in board["briefs"] if c["signal"] == "Hotspot")
        quiet = board["underheard"][0]
        return {
            "requests": f"{pulse['requests']:,}",
            "languages": str(pulse["languages"]),
            "districts": str(pulse["districts"]),
            "hotspots": str(pulse["hotspots"]),
            "unfunded": f"{pulse['unfunded_cr']:.0f}",
            "people": pulse["people_label"],
            "lead_place": f"{lead['district']}, {lead['state']}",
            "lead_need": f"{lead['sector_label']}  ·  {lead['scheme']}",
            "lead_score": str(lead["priority"]),
            "lead_pack": f"{lead['tranche_cr']:.1f}",
            "lead_line": f"{lead['allocated_cr']:.1f}",
            "quiet_place": f"{quiet['district']}, {quiet['state']}",
            "quiet_need": f"{quiet['sector_label']}  ·  {quiet['scheme']}",
            "quiet_cover": str(quiet["infra"]),
            "quiet_voice": str(int(round(quiet["voice"] * 100))),
            "quiet_records": str(quiet["requests"]),
        }
    except Exception:
        return fallback


def title(prs, icons):
    slide = blank(prs)
    rect(slide, 0, 0, 5.15, H, TEAL)
    slide.shapes.add_picture(str(icons["logo"]), Inches(1.35), Inches(1.35), Inches(2.45), Inches(2.45))
    text(slide, 0.7, 4.15, 3.8, 0.9, "JanSetu", 40, True, CREAM, font="Georgia", align=PP_ALIGN.CENTER)
    text(slide, 0.7, 5.05, 3.8, 0.45, "जनसेतु", 22, False, CREAM, font="Georgia", align=PP_ALIGN.CENTER)
    text(slide, 5.6, 1.55, 7.1, 0.4, "BUILD WITH AI  ·  CODE FOR COMMUNITIES", 13, True, GOLD)
    text(slide, 5.6, 2.05, 7.1, 1.8, "Citizen demand,\nplaced where public\nmoney is decided.", 36, False, INK, font="Georgia")
    text(
        slide, 5.6, 4.55, 6.8, 1.1,
        "A digital public good for India. People file infrastructure needs in their own language. A planning desk receives a short, explainable list.",
        18, False, MUTED,
    )
    text(slide, 5.6, 6.05, 6.8, 0.7, "Digital public infrastructure and governance\nTwelve languages  ·  Voice, text, and messaging", 15, False, TEAL_DEEP)


def problem(prs, icons, page, pages):
    slide = blank(prs)
    kicker(slide, "The problem")
    text(slide, 0.55, 0.68, 12, 1.1, "Requests and budgets\nlive in different places.", 36, False, INK, font="Georgia")
    text(slide, 0.55, 2.55, 12, 0.7, "Citizens already say what they need. The money for the year is decided somewhere else, on last year’s pattern.", 18, False, MUTED)
    cards = [
        ("Scattered asks", "Water, roads, clinics, and schools are reported on WhatsApp, missed-call lines, and portals that do not share a ledger."),
        ("Budgets follow habit", "Scheme lines tend to follow places that already have coverage and the capacity to spend, not the loudest unmet need."),
        ("No single room", "A planning desk cannot yet say, with evidence, whether this year’s rupees met this year’s ask."),
    ]
    for i, (head, body) in enumerate(cards):
        x = 0.55 + i * 4.15
        rect(slide, x, 3.5, 3.95, 2.85, CARD, rounded=True)
        rect(slide, x, 3.5, 0.1, 2.85, TERRA if i == 2 else TEAL)
        text(slide, x + 0.3, 3.7, 3.4, 0.7, head, 20, True, INK, font="Georgia")
        text(slide, x + 0.3, 4.5, 3.4, 1.55, body, 15, False, MUTED)
    footer(slide, icons, page, pages)


def product(prs, icons, page, pages):
    slide = blank(prs)
    kicker(slide, "The product")
    text(slide, 0.55, 0.68, 12, 0.9, "One ledger. Three moves.", 36, False, INK, font="Georgia")
    text(slide, 0.55, 1.7, 12, 0.6, "Every channel writes the same record: place, language, need, severity, and a reference the citizen can track.", 18, False, MUTED)
    steps = [
        ("01", "Hear", "Text, smartphone voice, a feature-phone missed call, SMS, or a messaging thread. Twelve Indian languages, including Hindi in Roman script."),
        ("02", "Place", "The record is read for language and need, then set beside population, rural share, deprivation, coverage, and the scheme line."),
        ("03", "Choose", "The desk gets hotspots, a shelf for quiet districts, and a cabinet note. The note helps a decision. It does not sanction money."),
    ]
    for i, (num, head, body) in enumerate(steps):
        y = 2.55 + i * 1.4
        rect(slide, 0.55, y, 12.2, 1.25, CARD, rounded=True)
        text(slide, 0.8, y + 0.28, 1.1, 0.7, num, 26, False, TERRA, font="Georgia", anchor=MSO_ANCHOR.MIDDLE)
        text(slide, 2.1, y + 0.15, 10, 0.4, head, 20, True, INK, font="Georgia")
        text(slide, 2.1, y + 0.58, 10.2, 0.55, body, 15, False, MUTED)
    footer(slide, icons, page, pages)


def channels(prs, icons, page, pages):
    slide = blank(prs)
    kicker(slide, "Intake")
    text(slide, 0.55, 0.68, 12, 0.8, "Four ways in. One row on the ledger.", 34, False, INK, font="Georgia")
    text(slide, 0.55, 1.6, 12, 0.55, "A missed call from a feature phone and a WhatsApp-style message become the same kind of evidence.", 18, False, MUTED)
    items = [
        (icons["chat"], "Text and SMS", "A written request, including a 160-character message, in the language people actually use."),
        (icons["mic"], "Voice", "Smartphone speech in the speaker’s language, or a keypad after a missed call."),
        (icons["water"], "Any need", "Water, roads, power, a clinic, a school, sanitation, a house, or a phone network."),
        (icons["road"], "Same record", "Place, language, sector, severity, channel, and a reference. Nothing else is required."),
    ]
    for i, (img, head, body) in enumerate(items):
        x = 0.45 + i * 3.2
        rect(slide, x, 2.5, 3.02, 4.15, CARD, rounded=True)
        slide.shapes.add_picture(str(img), Inches(x + 0.85), Inches(2.75), Inches(1.3), Inches(1.3))
        text(slide, x + 0.2, 4.2, 2.62, 0.6, head, 18, True, INK, font="Georgia", align=PP_ALIGN.CENTER)
        text(slide, x + 0.22, 4.9, 2.58, 1.4, body, 14, False, MUTED, align=PP_ALIGN.CENTER)
    footer(slide, icons, page, pages)


def score(prs, icons, page, pages):
    slide = blank(prs)
    kicker(slide, "The score")
    text(slide, 0.55, 0.68, 12, 0.7, "Four questions. Published weights.", 34, False, INK, font="Georgia")
    text(slide, 0.55, 1.5, 12, 0.55, "A tie between two needs is refused. The desk asks, rather than guessing.", 18, False, MUTED)
    parts = [
        ("34", "Demand", "How many people spoke, and how loud it is per lakh residents. A large district is not erased. A handful of messages cannot win alone."),
        ("30", "Deficit", "100 minus the coverage index. A district still off the drinking-water network scores higher than one that is mostly connected."),
        ("20", "Equity", "Rural share and deprivation. The same complaint carries more weight where people have less."),
        ("16", "Money", "Share of voice in that sector, minus share of the scheme line. Money that follows last year’s coverage shows up here."),
    ]
    for i, (num, head, body) in enumerate(parts):
        x = 0.45 + (i % 4) * 3.2
        rect(slide, x, 2.3, 3.02, 4.35, CARD, rounded=True)
        rect(slide, x, 2.3, 3.02, 0.12, TEAL if i < 3 else TERRA)
        text(slide, x + 0.2, 2.55, 2.6, 0.85, num, 40, False, TEAL_DEEP, font="Georgia")
        text(slide, x + 0.2, 3.45, 2.6, 0.45, head, 20, True, INK, font="Georgia")
        text(slide, x + 0.2, 4.05, 2.62, 2.2, body, 14, False, MUTED)
    footer(slide, icons, page, pages)


def desk(prs, icons, stats, page, pages):
    slide = blank(prs)
    kicker(slide, "The planning desk")
    text(slide, 0.55, 0.68, 12, 0.7, "What a minister can see in one screen.", 32, False, INK, font="Georgia")
    text(slide, 0.55, 1.5, 12, 0.5, "Figures are from the demonstration ledger, shaped from public scheme patterns. They are not official statistics.", 15, False, MUTED)
    tiles = [
        (stats["requests"], "Citizen records"),
        (stats["languages"], "Languages heard"),
        (stats["hotspots"], "Hotspots"),
        (f"₹{stats['unfunded']} Cr", "Short on the six notes"),
        (stats["people"], "People in those projects"),
    ]
    for i, (num, label) in enumerate(tiles):
        x = 0.45 + i * 2.55
        rect(slide, x, 2.25, 2.4, 2.15, TEAL if i == 3 else CARD, rounded=True)
        color = CREAM if i == 3 else INK
        label_color = CREAM if i == 3 else MUTED
        text(slide, x + 0.12, 2.45, 2.16, 0.95, num, 26, False, color, font="Georgia", align=PP_ALIGN.CENTER)
        text(slide, x + 0.15, 3.45, 2.1, 0.7, label, 13, False, label_color, align=PP_ALIGN.CENTER)
    text(
        slide, 0.55, 4.7, 12.2, 1.7,
        "The six notes are a portfolio: different needs, different states, plus one seat for a district that is badly served and barely heard.\n\n"
        "People named here are project beneficiaries. A person can appear in only one note on that list.",
        16, False, MUTED,
    )
    footer(slide, icons, page, pages)


def note(prs, icons, stats, page, pages):
    slide = blank(prs)
    kicker(slide, "A cabinet note")
    text(slide, 0.55, 0.68, 8, 0.8, stats["lead_place"], 34, False, INK, font="Georgia")
    text(slide, 0.55, 1.55, 8, 0.4, stats["lead_need"], 18, False, TEAL_DEEP)
    text(
        slide, 0.55, 2.15, 7.6, 1.3,
        "All-weather link roads for habitations cut off in the rain. The note explains the gap in plain language and shows the citizen records behind it.",
        16, False, MUTED,
    )
    facts = [
        (stats["lead_score"], "Priority"),
        (f"₹{stats['lead_pack']} Cr", "Indicative package"),
        (f"₹{stats['lead_line']} Cr", "Already on the scheme line"),
    ]
    for i, (num, label) in enumerate(facts):
        y = 3.6 + i * 1.05
        rect(slide, 0.55, y, 7.5, 0.92, CARD, rounded=True)
        text(slide, 0.8, y, 3.3, 0.92, num, 26, False, TERRA, font="Georgia", anchor=MSO_ANCHOR.MIDDLE)
        text(slide, 4.2, y, 3.5, 0.92, label, 16, False, MUTED, anchor=MSO_ANCHOR.MIDDLE)
    rect(slide, 8.4, 1.55, 4.4, 4.9, TEAL, rounded=True)
    slide.shapes.add_picture(str(icons["road"]), Inches(9.55), Inches(1.9), Inches(2.05), Inches(2.05))
    text(slide, 8.7, 4.15, 3.85, 1.9, "A decision aid.\nNot a sanction.", 26, False, CREAM, font="Georgia", align=PP_ALIGN.CENTER)
    footer(slide, icons, page, pages)


def quiet(prs, icons, stats, page, pages):
    slide = blank(prs)
    kicker(slide, "The under-heard shelf")
    text(slide, 0.55, 0.68, 12, 1.2, "A quiet ledger is not\na clean chit.", 36, False, INK, font="Georgia")
    text(
        slide, 0.55, 2.55, 7.4, 1.3,
        f"{stats['quiet_place']} is on this shelf for {stats['quiet_need'].split('  ·')[0].lower()}. Coverage is {stats['quiet_cover']} out of 100. Voice reach is {stats['quiet_voice']} percent. Only {stats['quiet_records']} records are on file.",
        18, False, MUTED,
    )
    points = [
        ("Shown as it is", "Sparse complaints are not multiplied to look like a crowd."),
        ("Still at the table", "High deficit and low voice earn a seat beside the hotspots."),
        ("Silence is weak evidence", "Where few people can file, quiet does not mean the need is met."),
    ]
    for i, (head, body) in enumerate(points):
        x = 0.55 + i * 4.15
        rect(slide, x, 4.15, 3.95, 2.35, CARD, rounded=True)
        text(slide, x + 0.25, 4.35, 3.45, 0.6, head, 18, True, INK, font="Georgia")
        text(slide, x + 0.25, 5.05, 3.45, 1.15, body, 15, False, MUTED)
    footer(slide, icons, page, pages)


def good(prs, icons, page, pages):
    slide = blank(prs)
    kicker(slide, "A digital public good")
    text(slide, 0.55, 0.68, 12, 0.8, "Readable. Optional model. No Aadhaar.", 32, False, INK, font="Georgia")
    text(slide, 0.55, 1.6, 12, 0.55, "The core engine runs on the server. Citizen text is not sent to a model vendor.", 18, False, MUTED)
    items = [
        ("No account", "A request needs a place and a need. A full phone number is never stored. The receipt is a reference."),
        ("Published method", "The four weights are fixed and the same for every state. Anyone can read why a district rose or fell."),
        ("Open ledger", "The demonstration data can be downloaded, without names."),
        ("Gemini stays optional", "If a key is set, it may rewrite a note from the published numbers only. The words of the citizen stay home."),
    ]
    for i, (head, body) in enumerate(items):
        x = 0.45 + (i % 2) * 6.4
        y = 2.4 + (i // 2) * 2.15
        rect(slide, x, y, 6.15, 1.95, CARD, rounded=True)
        text(slide, x + 0.3, y + 0.22, 5.55, 0.45, head, 20, True, INK, font="Georgia")
        text(slide, x + 0.3, y + 0.8, 5.55, 0.9, body, 15, False, MUTED)
    footer(slide, icons, page, pages)


def close(prs, icons):
    slide = blank(prs)
    rect(slide, 0, 0, W, H, TEAL)
    slide.shapes.add_picture(str(icons["logo"]), Inches(5.55), Inches(0.85), Inches(2.2), Inches(2.2))
    text(slide, 1.5, 3.25, 10.3, 0.8, "JanSetu", 44, False, CREAM, font="Georgia", align=PP_ALIGN.CENTER)
    text(slide, 2.2, 4.15, 8.9, 1.0, "Hear the country in the language it speaks.\nThen put that demand next to the money.", 20, False, CREAM, align=PP_ALIGN.CENTER)
    text(slide, 2.2, 5.7, 8.9, 0.8, "File a request  ·  Open the planning desk  ·  Read the method", 16, False, CREAM, align=PP_ALIGN.CENTER)


if __name__ == "__main__":
    build()
