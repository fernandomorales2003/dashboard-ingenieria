# app.py
import streamlit as st
import pandas as pd
import numpy as np
from zipfile import ZipFile
from io import BytesIO
import plotly.graph_objects as go
from fastkml import kml
from shapely.geometry import LineString, MultiLineString, Point, GeometryCollection, Polygon, MultiPolygon
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📶 Dashboard Ingeniería FTTH (fastkml)")
st.caption("TRONCAL/DERIV/PRECO + HUB/NAP/FOSC/NODOS + clientes simulados")

uploaded = st.file_uploader("📂 Subí tu archivo FTTH (.KMZ o .KML)", type=["kmz", "kml"])

# --- utilidades ---
LINE_LAYERS = ["TRONCAL", "DERIV", "PRECO"]
POINT_LAYERS = ["HUB", "NAP", "FOSC", "NODOS"]

LINE_COLORS = {"TRONCAL": "red", "DERIV": "green", "PRECO": "violet"}
POINT_STYLE = {
    "HUB":   {"color": "blue",   "size": 12, "symbol": "circle"},
    "NAP":   {"color": "red",    "size": 12, "symbol": "triangle-up"},
    "FOSC":  {"color": "black",  "size": 10, "symbol": "square"},
    "NODOS": {"color": "yellow", "size": 14, "symbol": "star"}
}

def read_kml_text(file):
    """Devuelve el texto KML desde un archivo .kml o dentro de un .kmz."""
    data = file.read()
    file.seek(0)
    if file.name.lower().endswith(".kmz"):
        with ZipFile(BytesIO(data)) as z:
            # Prioriza doc.kml; si no, el primer .kml
            names = z.namelist()
            kml_name = next((n for n in names if n.endswith("doc.kml")), None)
            if not kml_name:
                kml_name = next((n for n in names if n.lower().endswith(".kml")), None)
            if not kml_name:
                return None
            return z.read(kml_name)
    else:
        return data

def walk_features(feat, parents, out):
    """Recorre recursivamente Document/Folder/Placemark y acumula geometrías."""
    try:
        # Si es contenedor (Document/Folder)
        for f in feat.features():
            nm = getattr(f, "name", None) or ""
            walk_features(f, parents + [nm], out)
    except Exception:
        # Si es Placemark
        name = getattr(feat, "name", None) or ""
        geom = getattr(feat, "geometry", None)
        out.append({"path": parents, "name": name, "geom": geom, "raw": feat})

def is_layer(path_or_name, layer_key):
    """True si en la ruta o nombre aparece el texto de capa (case-insensitive)."""
    all_names = [str(x).upper() for x in (path_or_name if isinstance(path_or_name, list) else [path_or_name])]
    return any(layer_key in n for n in all_names)

def extract_lines_from_geom(geom):
    """Devuelve lista de LineString (lon,lat) desde geometrías varias."""
    lines = []
    if geom is None:
        return lines
    try:
        if isinstance(geom, LineString):
            lines.append(geom)
        elif isinstance(geom, MultiLineString):
            lines.extend(list(geom.geoms))
        elif isinstance(geom, GeometryCollection):
            for g in geom.geoms:
                lines.extend(extract_lines_from_geom(g))
        elif isinstance(geom, (Polygon, MultiPolygon)):
            # borde exterior como línea
            if isinstance(geom, Polygon):
                lines.append(LineString(geom.exterior.coords))
            else:
                for g in geom.geoms:
                    lines.append(LineString(g.exterior.coords))
    except Exception:
        pass
    return lines

def parse_gx_tracks(kml_text_bytes):
    """Fallback: extrae <gx:Track> como líneas (por si fastkml no las mapea)."""
    try:
        ns = {
            "kml": "http://www.opengis.net/kml/2.2",
            "gx": "http://www.google.com/kml/ext/2.2"
        }
        root = ET.fromstring(kml_text_bytes)
        tracks = []
        for pm in root.findall(".//kml:Placemark", ns):
            path_names = []
            # reconstruir ruta (sube a padres buscando <Folder><name>)
            parent = pm
            while True:
                parent = parent.getparent() if hasattr(parent, "getparent") else None
                if parent is None:
                    break

            # leer nombres ascendentes (si no hay lxml, omitimos ruta)
            # extraer gx:coord ó gx:Track/gx:coord
            coords = []
            for coord in pm.findall(".//gx:coord", ns):
                parts = coord.text.strip().split()
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    coords.append((lon, lat))
            if len(coords) >= 2:
                tracks.append({"path": [], "name": (pm.findtext("kml:name", default="", namespaces=ns) or ""), "coords": coords})
        return tracks
    except Exception:
        return []

def decide_layer(record):
    """Determina a qué capa FTTH pertenece un placemark por su ruta/nombre."""
    path = [p.upper() for p in record["path"]]
    nm = (record["name"] or "").upper()
    for key in LINE_LAYERS + POINT_LAYERS:
        if is_layer(path, key) or key in nm:
            return key
    return None

# --- app ---
if uploaded:
    kml_bytes = read_kml_text(uploaded)
    if not kml_bytes:
        st.error("❌ No se pudo leer el KML dentro del archivo.")
        st.stop()

    # 1) Parsear con fastkml
    k = kml.KML()
    k.from_string(kml_bytes)
    placemarks = []
    for doc in k.features():
        walk_features(doc, [getattr(doc, "name", "")], placemarks)

    # 2) Clasificar y extraer
    line_geoms = {key: [] for key in LINE_LAYERS}
    point_geoms = {key: [] for key in POINT_LAYERS}

    for rec in placemarks:
        layer = decide_layer(rec)
        if not layer:
            continue
        geom = rec["geom"]

        if layer in LINE_LAYERS:
            for ls in extract_lines_from_geom(geom):
                try:
                    lon, lat = list(ls.xy[0]), list(ls.xy[1])
                    if len(lon) >= 2 and len(lat) >= 2:
                        line_geoms[layer].append((lon, lat))
                except Exception:
                    continue
        elif layer in POINT_LAYERS:
            try:
                if isinstance(geom, Point):
                    point_geoms[layer].append((geom.x, geom.y))
            except Exception:
                continue

    # 3) Fallback: si no hubo líneas, intentar gx:Track en bruto
    if all(len(v) == 0 for v in line_geoms.values()):
        tracks = parse_gx_tracks(kml_bytes)
        # intentamos mapear por nombre
        for tr in tracks:
            nm = tr["name"].upper()
            mapped = next((key for key in LINE_LAYERS if key in nm), None)
            if not mapped:
                continue
            lon = [p[0] for p in tr["coords"]]
            lat = [p[1] for p in tr["coords"]]
            if len(lon) >= 2:
                line_geoms[mapped].append((lon, lat))

    # --- Reporte de capas detectadas
    st.write("**Resumen capas detectadas:**")
    st.write({k: len(v) for k, v in line_geoms.items()} | {k: len(v) for k, v in point_geoms.items()})

    # 4) Construir mapa
    fig = go.Figure()
    all_lat, all_lon = [], []

    # Líneas
    for layer in LINE_LAYERS:
        color = LINE_COLORS[layer]
        for lon, lat in line_geoms[layer]:
            if not lon or not lat:
                continue
            all_lat.extend(lat); all_lon.extend(lon)
            fig.add_trace(go.Scattermapbox(
                lon=lon, lat=lat, mode="lines",
                line=dict(width=3, color=color),
                name=layer
            ))

    # Puntos
    nap_coords = []
    for layer in POINT_LAYERS:
        pts = point_geoms[layer]
        if not pts:
            continue
        lons = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        all_lat.extend(lats); all_lon.extend(lons)
        style = POINT_STYLE[layer]
        fig.add_trace(go.Scattermapbox(
            lon=lons, lat=lats, mode="markers",
            marker=dict(size=style["size"], color=style["color"], symbol=style["symbol"]),
            name=layer
        ))
        if layer == "NAP":
            nap_coords = list(zip(lats, lons))

    # Clientes simulados alrededor de NAP
    if nap_coords:
        rng = np.random.default_rng()
        cl_lats, cl_lons, cl_pwr = [], [], []
        for lat, lon in nap_coords:
            n = rng.integers(3, 8)
            cl_lats.extend(lat + rng.uniform(-0.0005, 0.0005, n))
            cl_lons.extend(lon + rng.uniform(-0.0005, 0.0005, n))
            cl_pwr.extend(np.round(rng.uniform(-25, -17, n), 2))
        fig.add_trace(go.Scattermapbox(
            lon=cl_lons, lat=cl_lats, mode="markers",
            marker=dict(size=5, color="lightgray", opacity=0.7),
            name="Clientes simulados",
            text=[f"{p} dBm" for p in cl_pwr]
        ))

    # Centro y estilo
    if all_lat and all_lon:
        fig.update_layout(
            mapbox=dict(
                style="carto-positron",
                center=dict(lat=float(np.mean(all_lat)), lon=float(np.mean(all_lon))),
                zoom=14
            ),
            margin={"r":0,"t":0,"l":0,"b":0}
        )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Subí tu archivo FTTH (.KMZ / .KML) con carpetas: TRONCAL, DERIV, PRECO, HUB, NAP, FOSC, NODOS.")
