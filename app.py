import streamlit as st
import zipfile
import tempfile
import pandas as pd
import plotly.graph_objects as go
import xml.etree.ElementTree as ET
import random
import os

st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")

st.title("📡 Dashboard Ingeniería FTTH")
st.markdown("Subí el archivo `.kmz` o `.kml` para visualizar la red y sus componentes principales.")

uploaded_file = st.file_uploader("📁 Subir archivo KMZ/KML", type=["kmz", "kml"])

def parse_kml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2', 'gx': 'http://www.google.com/kml/ext/2.2'}

    troncales, fosc, nodos = [], [], []

    for placemark in root.iterfind(".//kml:Placemark", ns):
        name_tag = placemark.find("kml:name", ns)
        name = name_tag.text if name_tag is not None else "Sin nombre"

        line = placemark.find(".//kml:LineString/kml:coordinates", ns)
        point = placemark.find(".//kml:Point/kml:coordinates", ns)

        if line is not None:
            coords = [list(map(float, c.split(",")[:2])) for c in line.text.strip().split()]
            troncales.append(coords)
        elif point is not None:
            coord = list(map(float, point.text.strip().split(",")[:2]))
            if "FOSC" in name.upper():
                fosc.append(coord)
            elif "NOC" in name.upper() or "SHELTER" in name.upper():
                nodos.append(coord)

    return troncales, fosc, nodos

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".kml") as tmp:
        if uploaded_file.name.endswith(".kmz"):
            with zipfile.ZipFile(uploaded_file, "r") as kmz:
                for file in kmz.namelist():
                    if file.endswith(".kml"):
                        kmz.extract(file, tmp.name.replace(".kml", ""))
                        file_path = os.path.join(tmp.name.replace(".kml", ""), file)
                        break
        else:
            tmp.write(uploaded_file.read())
            file_path = tmp.name

    troncales, fosc, nodos = parse_kml(file_path)

    # Crear NAPs simuladas cerca de FOSC
    naps = []
    for fx, fy in fosc:
        for _ in range(random.randint(1, 3)):
            naps.append([fx + random.uniform(-0.0003, 0.0003), fy + random.uniform(-0.0003, 0.0003)])

    # Crear clientes simulados cerca de NAPs
    clientes = []
    potencias = []
    for nx, ny in naps:
        for _ in range(random.randint(3, 8)):
            cx = nx + random.uniform(-0.00015, 0.00015)
            cy = ny + random.uniform(-0.00015, 0.00015)
            clientes.append([cx, cy])
            potencias.append(round(random.uniform(-25, -17), 2))

    all_coords = [c for t in troncales for c in t] + fosc + nodos + naps
    lon_center = sum(c[0] for c in all_coords) / len(all_coords)
    lat_center = sum(c[1] for c in all_coords) / len(all_coords)

    # Métricas superiores
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Troncales", len(troncales))
    c2.metric("FOSC", len(fosc))
    c3.metric("NODOS", len(nodos))
    c4.metric("NAPs simuladas", len(naps))
    c5.metric("Clientes simulados", len(clientes))

    # Crear el mapa
    fig = go.Figure()

    for traza in troncales:
        lon, lat = zip(*traza)
        fig.add_trace(go.Scattermapbox(
            lon=lon, lat=lat, mode="lines",
            line=dict(width=3, color="red"),
            name="Troncal"
        ))

    if fosc:
        lon, lat = zip(*fosc)
        fig.add_trace(go.Scattermapbox(
            lon=lon, lat=lat, mode="markers",
            marker=dict(size=10, color="blue", symbol="square"),
            name="FOSC"
        ))

    if nodos:
        lon, lat = zip(*nodos)
        fig.add_trace(go.Scattermapbox(
            lon=lon, lat=lat, mode="markers",
            marker=dict(size=12, color="yellow", symbol="star"),
            name="NODOS"
        ))

    if naps:
        lon, lat = zip(*naps)
        fig.add_trace(go.Scattermapbox(
            lon=lon, lat=lat, mode="markers",
            marker=dict(size=9, color="purple", symbol="triangle"),
            name="NAPs"
        ))

    if clientes:
        lon, lat = zip(*clientes)
        fig.add_trace(go.Scattermapbox(
            lon=lon, lat=lat, mode="markers",
            marker=dict(size=6, color="green"),
            text=[f"{p} dBm" for p in potencias],
            name="Clientes"
        ))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=lat_center, lon=lon_center),
            zoom=13
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=700,
        legend=dict(x=0, y=1)
    )

    st.plotly_chart(fig, use_container_width=True)
