# app.py
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from zipfile import ZipFile
from io import BytesIO
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Dashboard Ingeniería FTTH (XML parser)", layout="wide")
st.title("📶 Dashboard Ingeniería FTTH")
st.caption("Parser XML directo: TRONCAL/DERIV/PRECO + HUB/NAP/FOSC/NODOS + clientes simulados")

# ----------------------------
# Config
# ----------------------------
LINE_LAYERS = ["TRONCAL", "DERIV", "PRECO"]
POINT_LAYERS = ["HUB", "NAP", "FOSC", "NODOS"]

LINE_COLORS = {"TRONCAL": "red", "DERIV": "green", "PRECO": "violet"}
POINT_STYLE = {
    "HUB":   {"color": "blue",   "size": 12, "symbol": "circle"},
    "NAP":   {"color": "red",    "size": 12, "symbol": "triangle-up"},
    "FOSC":  {"color": "black",  "size": 10, "symbol": "square"},
    "NODOS": {"color": "yellow", "size": 14, "symbol": "star"}
}

NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx":  "http://www.google.com/kml/ext/2.2"
}

# ----------------------------
# Utilidades
# ----------------------------
def get_kml_bytes(uploaded_file):
    """Devuelve bytes del .kml desde un .kml o dentro de un .kmz (prioriza doc.kml)."""
    raw = uploaded_file.read()
    uploaded_file.seek(0)
    name = uploaded_file.name.lower()
    if name.endswith(".kml"):
        return raw
    if name.endswith(".kmz"):
        with ZipFile(BytesIO(raw)) as z:
            names = z.namelist()
            kml_name = next((n for n in names if n.endswith("doc.kml")), None)
            if not kml_name:
                kml_name = next((n for n in names if n.lower().endswith(".kml")), None)
            if not kml_name:
                return None
            return z.read(kml_name)
    return None

def tag_eq(el, short):
    """Compara tag ignorando namespace."""
    if el is None or el.tag is None:
        return False
    if el.tag.endswith("}"+short):
        return True
    # sin namespace
    return el.tag == short

def text_of(el):
    return (el.text or "").strip() if el is not None else ""

def parse_coordinates_string(coord_text):
    """
    KML coordinates: "lon,lat[,alt] lon,lat[,alt] ..."
    Devuelve (lons[], lats[])
    """
    lons, lats = [], []
    if not coord_text:
        return lons, lats
    # separa por espacios y nuevos renglones
    for tup in coord_text.replace("\n", " ").replace("\t", " ").split():
        parts = tup.split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0]); lat = float(parts[1])
                lons.append(lon); lats.append(lat)
            except Exception:
                continue
    return lons, lats

def extract_geometries_from_placemark(pm):
    """
    Devuelve lista de dicts con geometría desde un Placemark.
    Cada item: {"type": "line"|"point", "lon": [...], "lat": [...]}  (para point, listas de 1)
    Soporta: LineString, Point, MultiGeometry, gx:Track
    """
    geoms = []

    # 1) LineString
    for ls in pm.findall(".//{*}LineString"):
        coords_el = ls.find(".//{*}coordinates")
        lons, lats = parse_coordinates_string(text_of(coords_el))
        if len(lons) >= 2:
            geoms.append({"type": "line", "lon": lons, "lat": lats})

    # 2) Point
    for pt in pm.findall(".//{*}Point"):
        coords_el = pt.find(".//{*}coordinates")
        lons, lats = parse_coordinates_string(text_of(coords_el))
        if len(lons) >= 1:
            geoms.append({"type": "point", "lon": [lons[0]], "lat": [lats[0]]})

    # 3) gx:Track (coords en <gx:coord> "lon lat alt")
    for tr in pm.findall(".//{"+NS["gx"]+"}Track"):
        lons, lats = [], []
        for c in tr.findall(".//{"+NS["gx"]+"}coord"):
            parts = text_of(c).split()
            if len(parts) >= 2:
                try:
                    lon = float(parts[0]); lat = float(parts[1])
                    lons.append(lon); lats.append(lat)
                except Exception:
                    continue
        if len(lons) >= 2:
            geoms.append({"type": "line", "lon": lons, "lat": lats})

    # 4) Polygons → usar borde exterior
    for poly in pm.findall(".//{*}Polygon"):
        outer = poly.find(".//{*}outerBoundaryIs/{*}LinearRing/{*}coordinates")
        lons, lats = parse_coordinates_string(text_of(outer))
        if len(lons) >= 2:
            geoms.append({"type": "line", "lon": lons, "lat": lats})

    # MultiGeometry ya está cubierto por los finds anteriores (buscan recursivo)
    return geoms

def walk_folder(el, path, out_list):
    """
    Recorre Document/Folder/Placemark y acumula:
      {"path": [...], "name": <placemark_name>, "geoms": [ ... ] }
    """
    if tag_eq(el, "Document") or tag_eq(el, "Folder"):
        name_el = el.find("{*}name")
        name = text_of(name_el)
        new_path = path + [name] if name else path
        # hijos
        for child in list(el):
            if tag_eq(child, "Folder") or tag_eq(child, "Document"):
                walk_folder(child, new_path, out_list)
            elif tag_eq(child, "Placemark"):
                pm_name = text_of(child.find("{*}name"))
                geoms = extract_geometries_from_placemark(child)
                if geoms:
                    out_list.append({"path": new_path, "name": pm_name, "geoms": geoms})
            # otros nodos: ignorar
    elif tag_eq(el, "Placemark"):
        pm_name = text_of(el.find("{*}name"))
        geoms = extract_geometries_from_placemark(el)
        if geoms:
            out_list.append({"path": path, "name": pm_name, "geoms": geoms})

def classify_layer(path, name):
    up = [p.upper() for p in path] + [(name or "").upper()]
    for key in LINE_LAYERS + POINT_LAYERS:
        if any(key in s for s in up):
            return key
    return None

# ----------------------------
# App
# ----------------------------
uploaded = st.file_uploader("📂 Subí tu archivo FTTH (.KMZ / .KML)", type=["kmz", "kml"])

if uploaded:
    kml_bytes = get_kml_bytes(uploaded)
    if not kml_bytes:
        st.error("❌ No se pudo extraer el KML del archivo.")
        st.stop()

    # Parse XML
    try:
        root = ET.fromstring(kml_bytes)
    except Exception as e:
        st.error(f"❌ Error al parsear XML KML: {e}")
        st.stop()

    # Recolectar placemarks con sus rutas
    placemarks = []
    walk_folder(root, [], placemarks)

    # Clasificar y separar
    lines = {k: [] for k in LINE_LAYERS}
    points = {k: [] for k in POINT_LAYERS}

    for rec in placemarks:
        layer = classify_layer(rec["path"], rec["name"])
        if not layer:
            continue
        for g in rec["geoms"]:
            if g["type"] == "line" and layer in LINE_LAYERS:
                if g["lon"] and g["lat"]:
                    lines[layer].append((g["lon"], g["lat"]))
            elif g["type"] == "point" and layer in POINT_LAYERS:
                points[layer].append((g["lon"][0], g["lat"][0]))

    # Debug rápido
    st.write("**Capas detectadas:**",
             {**{f"{k}_lineas": len(v) for k, v in lines.items()},
              **{f"{k}_puntos": len(v) for k, v in points.items()}})

    # Construir mapa
    fig = go.Figure()
    all_lat, all_lon = [], []

    # Líneas
    for layer in LINE_LAYERS:
        for lon, lat in lines[layer]:
            if not lon or not lat:
                continue
            all_lat.extend(lat); all_lon.extend(lon)
            fig.add_trace(go.Scattermapbox(
                lon=lon, lat=lat, mode="lines",
                line=dict(width=3, color=LINE_COLORS[layer]),
                name=layer
            ))

    # Puntos + NAP coords para clientes
    nap_coords = []
    for layer in POINT_LAYERS:
        pts = points[layer]
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

    # Centrar y mostrar
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
    st.info("Subí tu archivo FTTH con carpetas: TRONCAL, DERIV, PRECO, HUB, NAP, FOSC, NODOS.")
