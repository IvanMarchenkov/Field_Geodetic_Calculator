"""Экспорт ведомости координат: PDF, KML, веб-карта."""

from __future__ import annotations

import html
import os
import sys
import webbrowser
from datetime import datetime
from typing import Dict, List, Optional

from geodesic import format_dms

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(APP_DIR, "assets")
FONT_PATH = os.path.join(ASSETS_DIR, "fonts", "DejaVuSans.ttf")
FONT_BOLD_PATH = os.path.join(ASSETS_DIR, "fonts", "DejaVuSans-Bold.ttf")


def _font_paths():
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = [
        os.path.join(here, "assets", "fonts"),
        os.path.join(here, "fonts"),
        os.path.join(os.path.dirname(here), "assets", "fonts"),
    ]
    for folder in dirs:
        regular = os.path.join(folder, "DejaVuSans.ttf")
        if os.path.isfile(regular):
            return regular, os.path.join(folder, "DejaVuSans-Bold.ttf")
    return FONT_PATH, FONT_BOLD_PATH


def export_dir() -> str:
    override = os.environ.get("GEOCALC_EXPORT_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    target = os.path.join(APP_DIR, "exports")
    try:
        from android.storage import app_storage_path  # type: ignore

        target = os.path.join(app_storage_path(), "exports")
    except ImportError:
        pass
    os.makedirs(target, exist_ok=True)
    return target


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_pdf(points: List[Dict], meta: Dict) -> str:
    from fpdf import FPDF

    font_regular, font_bold = _font_paths()
    if not os.path.isfile(font_regular):
        raise FileNotFoundError("Не найден шрифт DejaVuSans.ttf для PDF")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.add_font("DejaVu", "", font_regular)
    bold_available = os.path.isfile(font_bold)
    if bold_available:
        pdf.add_font("DejaVu", "B", font_bold)

    pdf.set_text_color(30, 58, 95)
    pdf.set_font("DejaVu", "B" if bold_available else "", 16)
    pdf.cell(0, 10, "Ведомость координат", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(26, 26, 26)
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Эллипсоид: a = {meta['a']:.3f} м,  e² = {meta['e2']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        f"Станция (точка 1): B = {format_dms(meta['B1'])}   L = {format_dms(meta['L1'])}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        6,
        f"Исходное направление (точка 2): B = {format_dms(meta['B2'])}   L = {format_dms(meta['L2'])}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        6,
        f"Азимут A1 = {format_dms(meta['A1'])}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    col_w = [18, 55, 55, 52]
    headers = ["№", "Широта B", "Долгота L", "Примечание"]
    pdf.set_fill_color(30, 58, 95)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("DejaVu", "B" if bold_available else "", 9)
    for width, title in zip(col_w, headers):
        pdf.cell(width, 8, title, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_text_color(26, 26, 26)
    pdf.set_font("DejaVu", "", 8)
    fill_odd = (247, 246, 242)
    for i, point in enumerate(points):
        if i % 2 == 0:
            pdf.set_fill_color(*fill_odd)
        else:
            pdf.set_fill_color(255, 255, 255)
        note = point.get("note", "")
        row = [
            str(point["number"]),
            format_dms(point["B_deg"]),
            format_dms(point["L_deg"]),
            note,
        ]
        for width, text in zip(col_w, row):
            pdf.cell(width, 7, text, border=1, align="C", fill=True)
        pdf.ln()

    pdf.ln(3)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(
        0,
        5,
        "Точки с № 3 и далее вычислены решением прямой геодезической задачи "
        "(полярная засечка от точки 1). Азимут луча равен исходному азимуту A1, "
        "сложенному с горизонтальным углом строки.",
    )

    path = os.path.join(export_dir(), f"vedomost_{_stamp()}.pdf")
    pdf.output(path)
    return path


def write_kml(points: List[Dict], meta: Dict) -> str:
    def coord(point: Dict) -> str:
        return f"{point['L_deg']:.10f},{point['B_deg']:.10f},0"

    station = points[0]
    placemarks = []
    lines = []
    for point in points:
        description = (
            f"B = {format_dms(point['B_deg'])}<br/>"
            f"L = {format_dms(point['L_deg'])}<br/>"
            f"{html.escape(point.get('note', ''))}"
        )
        placemarks.append(
            f"""
      <Placemark>
        <name>Точка {point['number']}</name>
        <description><![CDATA[{description}]]></description>
        <Point><coordinates>{coord(point)}</coordinates></Point>
      </Placemark>"""
        )
        if point["number"] != 1:
            lines.append(
                f"""
      <Placemark>
        <name>1 – {point['number']}</name>
        <styleUrl>#ray</styleUrl>
        <LineString>
          <tessellate>1</tessellate>
          <coordinates>{coord(station)} {coord(point)}</coordinates>
        </LineString>
      </Placemark>"""
            )

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Геодезические точки</name>
    <description>Полярная засечка от точки 1, a = {meta['a']} м</description>
    <Style id="ray">
      <LineStyle><color>ff5f3a1e</color><width>2</width></LineStyle>
    </Style>
    {''.join(placemarks)}
    {''.join(lines)}
  </Document>
</kml>
"""
    path = os.path.join(export_dir(), f"points_{_stamp()}.kml")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(kml)
    return path


def write_map_html(points: List[Dict]) -> str:
    js_points = ",\n".join(
        "        {{id: {number}, lat: {B_deg}, lon: {L_deg}, note: {note}}}".format(
            number=point["number"],
            B_deg=point["B_deg"],
            L_deg=point["L_deg"],
            note=repr(point.get("note", "")),
        )
        for point in points
    )
    center_lat = sum(p["B_deg"] for p in points) / len(points)
    center_lon = sum(p["L_deg"] for p in points) / len(points)
    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Карта точек</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    html, body, #map {{ margin: 0; height: 100%; }}
    .leaflet-container {{ font-family: Georgia, "Times New Roman", serif; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const points = [
{js_points}
    ];
    const map = L.map('map').setView([{center_lat}, {center_lon}], 12);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap'
    }}).addTo(map);
    const station = points.find(p => p.id === 1) || points[0];
    const group = [];
    points.forEach(p => {{
      const marker = L.marker([p.lat, p.lon]).addTo(map);
      marker.bindPopup('<b>Точка ' + p.id + '</b><br/>' + p.note);
      group.push(marker);
      if (p.id !== station.id) {{
        L.polyline([[station.lat, station.lon], [p.lat, p.lon]], {{
          color: '#1e3a5f', weight: 2
        }}).addTo(map);
      }}
    }});
    map.fitBounds(L.featureGroup(group).getBounds().pad(0.2));
  </script>
</body>
</html>
"""
    path = os.path.join(export_dir(), f"map_{_stamp()}.html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
    return path


def open_path(path: str, mime: Optional[str] = None) -> None:
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
        return

    try:
        from jnius import autoclass, cast  # type: ignore

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        File = autoclass("java.io.File")
        StrictMode = autoclass("android.os.StrictMode")
        StrictMode.setVmPolicy(StrictMode.VmPolicy.Builder().build())
        uri = Uri.fromFile(File(path))
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(uri, mime or _guess_mime(path))
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        current = cast("android.content.Context", PythonActivity.mActivity)
        current.startActivity(intent)
        return
    except Exception:
        pass

    webbrowser.open("file:///" + path.replace("\\", "/"))


def _guess_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".pdf": "application/pdf",
        ".kml": "application/vnd.google-earth.kml+xml",
        ".html": "text/html",
        ".htm": "text/html",
    }.get(ext, "*/*")
