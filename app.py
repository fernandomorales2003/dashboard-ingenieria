import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import tempfile, zipfile, os, xmltodict, random

st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📡 Dashboard Ingeniería FTTH")
st.markdown("Subí tu archivo `.kmz`, `.kml` o `.rtf` para visualizar el plano de ingeniería con sus troncales, derivaciones, HUB, NAP, etc.")

uploaded_file = st.file_uploader("📁 Subir archivo", type=["kmz", "kml", "rtf"])

def extract_kml(uploaded_file):
    """Extrae el texto KML desde KMZ, KML o RTF"""
    temp = tempfile.NamedTemporaryFile(delete=False)
    temp.write(uploaded_file.read())
    temp.flush()
    path = temp.name

    if uploaded_file.name.endswith(".kmz"):
        with zipfile.ZipFile(path, "r") as kmz:
            for name in kmz.namelist():
                if name.endswith(".kml"):
                    extracted_path = os.path.join(tempfile.gettempdir(), name)
                    kmz.extract(name, tempfile.gettempdir())
                    return extracted_path
    elif uploaded_file.name.endswith(".kml"):
        return path
    elif uploaded_file.name.endswith(".rtf"):
        # Extraer el contenido KML desde un RTF exportado
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        start = content.find("<kml")
        end = content.rfind("</kml>")
        if start != -1 and end != -1:
            kml_text = content[start:end+6]
            kml_path = path + ".kml"
            with open(kml_path, "w", encoding="utf-8") as f:
                f.write(kml_text)
            return kml_path
    return None

def parse_kml(kml_path):
    """Lee el KML y clasifica coordenadas por capa"""
    with open(kml_path, "r", encoding="utf-8") as f:
        kml_dict = xmltodict.parse(f.read())

    capas = {"TRONCALES": [], "DERIVACION": [], "PRECON": [], "HUB": [], "NAP": [], "FOSC": [], "NODOS": []}

    def recorrer(node, current_folder=None):
        if isinstance(node, dict):
            if "Folder" in node:
                folders = node["Folder"] if isinstance(node["Folder"], list) else [node["Folder"]]
                for f in folders:
                    nombre = f.get("name", "").upper()
                    recorrer(f, nombre)
            if "Placemark" in node:
                placemarks = node["Placemark"] if isinstance(node["Placemark"], list) else [node["Placemark"]]
                for p in placemarks:
                    coords = None
                    if "LineString" in p and "coordinates" in p["LineString"]:
                        coords = p["LineString"]["coordinates"]
                        tipo = current_folder or "TRONCALES"
                    elif "Point" in p and "coordinates" in p["Point"]:
                        coords = p["Point"]["coordinates"]
                        tipo = current_folder or "NODOS"
                    else:
                        continue

                    # Normalizar coordenadas
                    if coords:
                        coords = [list(map(float, c.split(",")[:2])) for c in coords.strip().split()]
                        if tipo:
                            tipo_key = next((k for k in capas.keys() if k in tipo.upper()), None)
                            if tipo_key:
                                capas[tipo_key].append(coords)

    recorrer(kml_dict)
    return capas

if uploaded_file:
    kml_path = extract_kml(uploaded_file)
    if not kml_path:
        st.error("No se pudo extraer el KML del archivo.")
        st.stop()

    capas = parse_kml(kml_path)
    all_coords = [pt for lista in capas.values() for seg in lista for pt in seg]
    if not all_coords:
        st.error("No se encontraron coordenadas válidas en el archivo.")
        st.stop()

    lon_center = sum(p[0] for p in all_coords) / len(all_coords)
    lat_center = sum(p[1] for p in all_coords) / len(all_coords)

    # Simular NAP y clientes
    naps = capas["NAP"]
    if naps:
        clientes = []
        potencias = []
        for nap in naps:
            for (x, y) in nap:
                for _ in range(random.randint(3, 8)):
                    cx = x + random.uniform(-0.0002, 0.0002)
                    cy = y + random.uniform(-0.0002, 0.0002)
                    clientes.append([cx, cy])
                    potencias.append(round(random.uniform(-25, -17), 2))
    else:
        clientes, potencias = [], []

    # ---- Resumen Superior ----
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Troncales", len(capas["TRONCALES"]))
    c2.metric("Derivaciones", len(capas["DERIVACION"]))
    c3.metric("Precon", len(capas["PRECON"]))
    c4.metric("HUB", len(capas["HUB"]))
    c5.metric("NAP", len(capas["NAP"]))
    c6.metric("FOSC", len(capas["FOSC"]))
    c7.metric("Clientes", len(clientes))

    # ---- Crear mapa ----
    fig = go.Figure()

    colores = {
        "TRONCALES": "red",
        "DERIVACION": "orange",
        "PRECON": "purple",
        "HUB": "blue",
        "NAP": "violet",
        "FOSC": "yellow",
        "NODOS": "gray"
    }

    # Líneas
    for tipo, segmentos in capas.items():
        for seg in segmentos:
            if len(seg) > 1:
                lon, lat = zip(*seg)
                fig.add_trace(go.Scattermapbox(
                    lon=lon, lat=lat, mode="lines",
                    line=dict(width=3 if tipo == "TRONCALES" else 2, color=colores[tipo]),
                    name=tipo
                ))

    # Puntos
    for tipo in ["HUB", "NAP", "FOSC", "NODOS"]:
        if capas[tipo]:
            lon = [p[0][0] for p in capas[tipo]]
            lat = [p[0][1] for p in capas[tipo]]
            fig.add_trace(go.Scattermapbox(
                lon=lon, lat=lat, mode="markers",
                marker=dict(size=10, color=colores[tipo], symbol="circle"),
                name=tipo
            ))

    # Clientes simulados
    if clientes:
        lon, lat = zip(*clientes)
        fig.add_trace(go.Scattermapbox(
            lon=lon, lat=lat, mode="markers",
            marker=dict(size=6, color="lime"),
            text=[f"{p} dBm" for p in potencias],
            name="Clientes"
        ))

    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=lat_center, lon=lon_center),
            zoom=13
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=700,
        legend=dict(x=0, y=1)
    )

    st.plotly_chart(fig, use_container_width=True)

