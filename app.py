import streamlit as st
import pydeck as pdk
import numpy as np
import pandas as pd
from zipfile import ZipFile
from io import BytesIO
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📶 Dashboard Ingeniería FTTH")
st.caption("Visualización de trazas, HUB, NAP, FOSC, NODOS y clientes simulados")

LINE_LAYERS = ["TRONCAL", "DERIV", "PRECO"]
POINT_LAYERS = ["HUB", "NAP", "FOSC", "NODOS"]
LINE_COLORS = {"TRONCAL": [255, 0, 0], "DERIV": [0, 255, 0], "PRECO": [150, 0, 255]}
POINT_COLORS = {"HUB": [0, 100, 255], "NAP": [255, 0, 0], "FOSC": [0, 0, 0], "NODOS": [255, 255, 0]}

def extract_kml_bytes(uploaded_file):
    raw = uploaded_file.read()
    uploaded_file.seek(0)
    if uploaded_file.name.lower().endswith(".kmz"):
        with ZipFile(BytesIO(raw)) as z:
            kml_name = next((n for n in z.namelist() if n.endswith(".kml")), None)
            return z.read(kml_name)
    return raw

def parse_coordinates_string(coord_text):
    coords = []
    if not coord_text:
        return coords
    for tup in coord_text.replace("\n", " ").split():
        parts = tup.split(",")
        if len(parts) >= 2:
            try:
                lon, lat = float(parts[0]), float(parts[1])
                coords.append((lat, lon))
            except:
                pass
    return coords

def extract_from_kml(kml_bytes):
    root = ET.fromstring(kml_bytes)
    placemarks = []
    for pm in root.findall(".//{*}Placemark"):
        name = (pm.findtext(".//{*}name") or "").upper()
        coords = []
        geom_type = None

        # LineString
        for ls in pm.findall(".//{*}LineString"):
            coord_text = ls.findtext(".//{*}coordinates")
            coords = parse_coordinates_string(coord_text)
            geom_type = "line"

        # Point
        for pt in pm.findall(".//{*}Point"):
            coord_text = pt.findtext(".//{*}coordinates")
            coords = parse_coordinates_string(coord_text)
            geom_type = "point"

        if coords:
            placemarks.append({"name": name, "geom_type": geom_type, "coords": coords})
    return placemarks

uploaded = st.file_uploader("📂 Subí tu archivo FTTH (.KMZ / .KML)", type=["kmz", "kml"])

if uploaded:
    kml_bytes = extract_kml_bytes(uploaded)
    if not kml_bytes:
        st.error("❌ No se pudo leer el archivo.")
        st.stop()

    placemarks = extract_from_kml(kml_bytes)
    if not placemarks:
        st.error("❌ No se detectaron geometrías en el archivo.")
        st.stop()

    # Clasificación
    lines, points = [], []
    for pm in placemarks:
        name = pm["name"]
        if any(k in name for k in LINE_LAYERS):
            layer = next(k for k in LINE_LAYERS if k in name)
            color = LINE_COLORS[layer]
            coords = pm["coords"]
            for i in range(len(coords)-1):
                lines.append({"layer": layer, "color": color, "from": coords[i][::-1], "to": coords[i+1][::-1]})
        elif any(k in name for k in POINT_LAYERS):
            layer = next(k for k in POINT_LAYERS if k in name)
            color = POINT_COLORS[layer]
            lat, lon = coords[0]
            points.append({"layer": layer, "color": color, "lat": lat, "lon": lon})

    df_lines = pd.DataFrame(lines)
    df_points = pd.DataFrame(points)

    # Clientes simulados alrededor de NAP
    nap_points = df_points[df_points["layer"] == "NAP"]
    clientes = []
    if not nap_points.empty:
        rng = np.random.default_rng()
        for _, row in nap_points.iterrows():
            for _ in range(rng.integers(3, 8)):
                clientes.append({
                    "lat": row.lat + rng.uniform(-0.0005, 0.0005),
                    "lon": row.lon + rng.uniform(-0.0005, 0.0005),
                    "color": [200, 200, 200],
                    "pot": f"{rng.uniform(-25, -17):.2f} dBm"
                })
    df_clientes = pd.DataFrame(clientes)

    # --- Capas PyDeck
    line_layer = pdk.Layer(
        "LineLayer",
        data=df_lines,
        get_source_position="from",
        get_target_position="to",
        get_color="color",
        get_width=4,
    )

    point_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_points,
        get_position='[lon, lat]',
        get_color="color",
        get_radius=8,
        pickable=True,
        tooltip=True,
    )

    cliente_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_clientes,
        get_position='[lon, lat]',
        get_color="color",
        get_radius=4,
        pickable=True,
        get_tooltip="pot"
    ) if not df_clientes.empty else None

    layers = [line_layer, point_layer]
    if cliente_layer:
        layers.append(cliente_layer)

    # Vista centrada
    if not df_points.empty:
        lat_center = df_points["lat"].mean()
        lon_center = df_points["lon"].mean()
    else:
        lat_center, lon_center = -35.47, -69.57

    view_state = pdk.ViewState(latitude=lat_center, longitude=lon_center, zoom=13)
    tooltip = {"html": "<b>{layer}</b><br/>Lat: {lat}<br/>Lon: {lon}", "style": {"backgroundColor": "white"}}

    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state, tooltip=tooltip))

else:
    st.info("Subí un archivo FTTH (.KMZ o .KML) con carpetas: TRONCAL, DERIV, PRECO, HUB, NAP, FOSC, NODOS.")
