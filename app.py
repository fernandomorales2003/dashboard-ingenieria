import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import tempfile, zipfile, os, xmltodict, random

st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📡 Dashboard Ingeniería FTTH")

uploaded_file = st.file_uploader("📁 Subir archivo KMZ/KML/RTF", type=["kmz", "kml", "rtf"])

# ----------- EXTRACCIÓN ----------
def extract_kml(uploaded_file):
    temp = tempfile.NamedTemporaryFile(delete=False)
    temp.write(uploaded_file.read())
    temp.flush()
    path = temp.name

    if uploaded_file.name.endswith(".kmz"):
        with zipfile.ZipFile(path, "r") as kmz:
            for name in kmz.namelist():
                if name.endswith(".kml"):
                    extracted = os.path.join(tempfile.gettempdir(), name)
                    kmz.extract(name, tempfile.gettempdir())
                    return extracted
    elif uploaded_file.name.endswith(".kml"):
        return path
    elif uploaded_file.name.endswith(".rtf"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        start, end = content.find("<kml"), content.rfind("</kml>")
        if start != -1 and end != -1:
            kml_text = content[start:end+6]
            kml_path = path + ".kml"
            with open(kml_path, "w", encoding="utf-8") as f:
                f.write(kml_text)
            return kml_path
    return None


# ----------- PARSEO ROBUSTO ----------
def parse_kml(kml_path):
    with open(kml_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        kml_dict = xmltodict.parse(content)
    except Exception:
        st.error("No se pudo leer el archivo KML.")
        return {k: [] for k in ["TRONCAL", "DERIVACION", "PRECON", "HUB", "NAP", "FOSC", "NODOS"]}

    capas = {k: [] for k in ["TRONCAL", "DERIVACION", "PRECON", "HUB", "NAP", "FOSC", "NODOS"]}

    def buscar(nodo, carpeta=""):
        if isinstance(nodo, dict):
            for key, value in nodo.items():
                if key == "Folder":
                    lst = value if isinstance(value, list) else [value]
                    for f in lst:
                        nombre = str(f.get("name", "")).upper()
                        buscar(f, carpeta=nombre)
                elif key == "Placemark":
                    placemarks = value if isinstance(value, list) else [value]
                    for p in placemarks:
                        coords_text = None
                        if "LineString" in p and "coordinates" in p["LineString"]:
                            coords_text = p["LineString"]["coordinates"]
                        elif "Point" in p and "coordinates" in p["Point"]:
                            coords_text = p["Point"]["coordinates"]

                        if coords_text:
                            try:
                                coords = [list(map(float, c.split(",")[:2])) for c in coords_text.strip().split()]
                            except Exception:
                                continue

                            nombre_punto = str(p.get("name", "")).strip()
                            nombre_carpeta = carpeta.upper()
                            tipo = "NODOS"
                            if "TRONCAL" in nombre_carpeta: tipo = "TRONCAL"
                            elif "DERIV" in nombre_carpeta: tipo = "DERIVACION"
                            elif "PRE" in nombre_carpeta: tipo = "PRECON"
                            elif "HUB" in nombre_carpeta: tipo = "HUB"
                            elif "NAP" in nombre_carpeta: tipo = "NAP"
                            elif "FOSC" in nombre_carpeta: tipo = "FOSC"

                            capas[tipo].append({"coords": coords, "name": nombre_punto})

                elif isinstance(value, (dict, list)):
                    buscar(value, carpeta)

    buscar(kml_dict)
    return capas


# ----------- APP PRINCIPAL ----------
if uploaded_file:
    kml_path = extract_kml(uploaded_file)
    if not kml_path:
        st.error("❌ No se pudo extraer el archivo KML.")
        st.stop()

    capas = parse_kml(kml_path)
    all_coords = [pt for lista in capas.values() for seg in lista for pt in seg["coords"]]

    if not all_coords:
        st.warning("⚠️ No se encontraron coordenadas válidas.")
        st.json({k: len(v) for k, v in capas.items()})
        st.stop()

    lon_center = sum(p[0] for p in all_coords) / len(all_coords)
    lat_center = sum(p[1] for p in all_coords) / len(all_coords)

    # ---------- SIMULACIÓN DE CLIENTES ----------
    clientes, potencias = [], []
    for nap in capas["NAP"]:
        for (x, y) in nap["coords"]:
            for _ in range(random.randint(3, 6)):
                cx, cy = x + random.uniform(-0.00025, 0.00025), y + random.uniform(-0.00025, 0.00025)
                clientes.append([cx, cy])
                potencias.append(round(random.uniform(-25, -17), 2))

    # ---------- MÉTRICAS ----------
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Troncales", len(capas["TRONCAL"]))
    c2.metric("Derivaciones", len(capas["DERIVACION"]))
    c3.metric("Preconectorizado", len(capas["PRECON"]))
    c4.metric("HUB", len(capas["HUB"]))
    c5.metric("NAP", len(capas["NAP"]))
    c6.metric("FOSC", len(capas["FOSC"]))
    c7.metric("Clientes", len(clientes))

    # ---------- MAPA ----------
    fig = go.Figure()
    colores = {
        "TRONCAL": "red",
        "DERIVACION": "green",
        "PRECON": "violet",
        "HUB": "blue",
        "NAP": "magenta",
        "FOSC": "yellow",
        "NODOS": "gray"
    }

    # === LINEAS ===
    for tipo in ["TRONCAL", "DERIVACION", "PRECON"]:
        all_lon, all_lat = [], []
        for seg in capas[tipo]:
            coords = seg["coords"]
            if len(coords) > 1:
                lon, lat = zip(*coords)
                all_lon += [None] + list(lon)
                all_lat += [None] + list(lat)
        if all_lon:
            fig.add_trace(go.Scattermapbox(
                lon=all_lon, lat=all_lat, mode="lines",
                line=dict(width=3, color=colores[tipo]),
                name=tipo,
                hoverinfo="none",
            ))

    # === PUNTOS ===
    simbolos = {
        "HUB": "diamond",
        "NAP": "triangle-up",
        "FOSC": "circle",
        "NODOS": "square"
    }
    tamaños = {
        "HUB": 16,
        "NAP": 13,
        "FOSC": 11,
        "NODOS": 10
    }

    for tipo in ["HUB", "NAP", "FOSC", "NODOS"]:
        if capas.get(tipo):
            lon, lat, nombres = [], [], []
            for seg in capas[tipo]:
                if seg and seg.get("coords"):
                    lon.append(seg["coords"][0][0])
                    lat.append(seg["coords"][0][1])
                    nombres.append(seg.get("name", f"{tipo}_{len(nombres)+1}"))

            if lon and lat:
                fig.add_trace(go.Scattermapbox(
                    lon=lon, lat=lat,
                    mode="markers+text" if tipo == "HUB" else "markers",
                    text=nombres if tipo == "HUB" else None,
                    textposition="top right",
                    marker=dict(
                        size=tamaños.get(tipo, 10),
                        color=colores.get(tipo, "white"),
                        symbol=simbolos.get(tipo, "circle"),
                        line=dict(width=1, color="white")
                    ),
                    name=tipo,
                    hoverinfo="text",
                ))

    # === CLIENTES ===
    if clientes:
        lon, lat = zip(*clientes)
        fig.add_trace(go.Scattermapbox(
            lon=lon, lat=lat, mode="markers",
            marker=dict(size=5, color="lime"),
            text=[f"{p} dBm" for p in potencias],
            name="Clientes (Simulados)",
            hoverinfo="text",
            visible="legendonly",
        ))

    # === CONFIG MAPA ===
    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=lat_center, lon=lon_center),
            zoom=12.8
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=720,
        legend=dict(x=0, y=1),
    )

    st.plotly_chart(fig, use_container_width=True)
