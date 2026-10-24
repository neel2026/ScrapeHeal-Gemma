"""Built-in, deterministic demo scenarios for ScrapeHeal-Gemma."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Preset:
    key: str
    title: str
    subtitle: str
    broken_selector: str
    goal: str
    html: str
    image: Image.Image
    row_selector: str
    field_selectors: Dict[str, str]
    records: List[Dict[str, str]]

    @property
    def xpath(self) -> str:
        if self.key == "football_league":
            return '//div[@data-testid="club-standing-card" and contains(concat(" ", normalize-space(@class), " "), " club-row-grid-2026 ")]'
        if self.key == "cloud_gpu":
            return '//article[contains(concat(" ", normalize-space(@class), " "), " gpu-card-row ")]'
        return '//section[contains(concat(" ", normalize-space(@class), " "), " b2b-machine-card ")]'


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _screenshot(title: str, subtitle: str, columns: List[str], rows: List[List[str]]) -> Image.Image:
    image = Image.new("RGB", (1200, 780), "#0b1020")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1200, 72), fill="#111a2e")
    draw.ellipse((28, 27, 44, 43), fill="#58e0bd")
    draw.text((60, 22), "NORTHSTAR / LIVE DATA", font=_font(18, True), fill="#e7efff")
    draw.text((1000, 25), "● SYSTEM ONLINE", font=_font(13, True), fill="#58e0bd")
    draw.text((42, 106), title, font=_font(31, True), fill="#f4f7ff")
    draw.text((44, 150), subtitle, font=_font(16), fill="#98a6c4")

    card_top = 205
    draw.rounded_rectangle((36, card_top, 1164, 738), radius=18, fill="#111a2b", outline="#27344d", width=2)
    col_widths = [len(column) for column in columns]
    total = sum(col_widths)
    widths = [int(1080 * width / total) for width in col_widths]
    widths[-1] += 1080 - sum(widths)
    starts = [58]
    for width in widths[:-1]:
        starts.append(starts[-1] + width)
    draw.rectangle((38, card_top + 2, 1162, card_top + 54), fill="#18243a")
    for x, label in zip(starts, columns):
        draw.text((x, card_top + 19), label.upper(), font=_font(12, True), fill="#8798b8")

    row_height = 86
    for index, row in enumerate(rows):
        top = card_top + 55 + index * row_height
        if index % 2 == 1:
            draw.rectangle((39, top, 1161, top + row_height), fill="#131e31")
        draw.line((58, top + row_height - 1, 1142, top + row_height - 1), fill="#26324a", width=1)
        for column_index, (x, value) in enumerate(zip(starts, row)):
            color = "#f0f4ff" if column_index == 0 else "#b8c5db"
            font = _font(15, column_index == 0)
            draw.text((x, top + 31), value, font=font, fill=color)
    return image


def _make_html(rows: List[Dict[str, str]], row_class: str, fields: Dict[str, str], extra: str = "", row_tag: str = "article") -> str:
    cards = []
    for row in rows:
        values = "".join(
            f'<div class="field"><span>{escape(label)}</span><strong data-field="{escape(key)}">{escape(row[key])}</strong></div>'
            for key, label in fields.items()
        )
        cards.append(f'<{row_tag} class="{row_class}" {extra.format(**{key: escape(value) for key, value in row.items()})}>{values}</{row_tag}>')
    return '<!doctype html><html><head><title>Modernized listing</title><script>tracking()</script><style>.legacy{}</style></head><body><main>' + "".join(cards) + "</main></body></html>"


PRESETS = {
    "football_league": "UK Football Standings",
    "cloud_gpu": "CloudGPU Marketplace",
    "industrial_b2b": "Industrial B2B Catalog",
}


def build_preset(name: str) -> Preset:
    if name == "football_league":
        fields = {"club": "Club", "played": "P", "goal_difference": "GD", "points": "Pts", "form": "Form"}
        records = [
            {"club": "Canvey Island FC", "played": "12", "goal_difference": "+18", "points": "29", "form": "W W D W W"},
            {"club": "Hornchurch FC", "played": "12", "goal_difference": "+15", "points": "27", "form": "W D W W W"},
            {"club": "Chatham Town", "played": "12", "goal_difference": "+11", "points": "24", "form": "L W W D W"},
            {"club": "Hashtag United", "played": "12", "goal_difference": "+8", "points": "22", "form": "D W W L W"},
            {"club": "Billericay Town", "played": "12", "goal_difference": "+5", "points": "20", "form": "W L D W D"},
        ]
        title, subtitle = "Isthmian Premier Division", "2026 / 27  •  League table  •  Updated 2 min ago"
        screenshot_rows = [[r["club"], r["played"], r["goal_difference"], r["points"], r["form"]] for r in records]
        image = _screenshot(title, subtitle, ["Club", "P", "GD", "Pts", "Form"], screenshot_rows)
        html = _make_html(records, "club-row-grid-2026", fields, 'data-testid="club-standing-card" data-club="{club}"', row_tag="div")
        return Preset("football_league", "UK Non-League Football Club Standings & Stats", subtitle, "table.league-standings-v1 tbody tr", "Extract club, played, goal difference, points, and recent form.", html, image, 'div[data-testid="club-standing-card"].club-row-grid-2026', {key: f'[data-field="{key}"]' for key in fields}, records)

    if name == "cloud_gpu":
        fields = {"gpu_model": "GPU Model", "vram": "VRAM", "price": "Spot Price/hr", "availability": "Nodes Available"}
        records = [
            {"gpu_model": "NVIDIA H100 SXM", "vram": "80 GB", "price": "$2.84", "availability": "18 regions / 42 nodes"},
            {"gpu_model": "NVIDIA A100 PCIe", "vram": "80 GB", "price": "$1.12", "availability": "24 regions / 86 nodes"},
            {"gpu_model": "AMD MI300X", "vram": "192 GB", "price": "$1.76", "availability": "7 regions / 19 nodes"},
            {"gpu_model": "NVIDIA L40S", "vram": "48 GB", "price": "$0.68", "availability": "31 regions / 124 nodes"},
        ]
        title, subtitle = "Spot GPU Inventory", "On-demand capacity  •  Prices in USD  •  Live market snapshot"
        image = _screenshot(title, subtitle, ["GPU Model", "VRAM", "Spot Price / hr", "Nodes Available"], [[r["gpu_model"], r["vram"], r["price"], r["availability"]] for r in records])
        html = _make_html(records, "gpu-card-row", fields, 'data-sku="{gpu_model}"')
        return Preset("cloud_gpu", "CloudGPU Spot Instance Marketplace", subtitle, "table#gpu-pricing-legacy tr.instance-row", "Extract model, VRAM, hourly spot price, and node availability.", html, image, "article.gpu-card-row", {key: f'[data-field="{key}"]' for key in fields}, records)

    if name == "industrial_b2b":
        fields = {"equipment": "Equipment Name", "power": "Power Rating", "lead_time": "Lead Time", "unit_price": "Unit Price (INR)"}
        records = [
            {"equipment": "CNC Vertical Machining Center", "power": "22 kW", "lead_time": "6–8 weeks", "unit_price": "₹ 4,850,000"},
            {"equipment": "Servo Hydraulic Press 160T", "power": "18.5 kW", "lead_time": "4–5 weeks", "unit_price": "₹ 2,240,000"},
            {"equipment": "Industrial Laser Cutter 3kW", "power": "32 kW", "lead_time": "8–10 weeks", "unit_price": "₹ 6,125,000"},
            {"equipment": "Precision Surface Grinder", "power": "7.5 kW", "lead_time": "3–4 weeks", "unit_price": "₹ 1,375,000"},
        ]
        title, subtitle = "Precision Machinery Catalog", "Ahmedabad Industrial Supply  •  GST excluded  •  Quote validity: 30 days"
        image = _screenshot(title, subtitle, ["Equipment", "Power", "Lead Time", "Unit Price"], [[r["equipment"], r["power"], r["lead_time"], r["unit_price"]] for r in records])
        html = _make_html(records, "b2b-machine-card", fields, 'data-part-id="{equipment}"', row_tag="section")
        return Preset("industrial_b2b", "Industrial Engineering & B2B Machinery Catalog", subtitle, "ul.product-catalog-old li.item-box", "Extract equipment name, power rating, lead time, and unit price in INR.", html, image, "section.b2b-machine-card", {key: f'[data-field="{key}"]' for key in fields}, records)

    raise ValueError(f"Unknown preset {name!r}. Choose one of: {', '.join(PRESETS)}")
