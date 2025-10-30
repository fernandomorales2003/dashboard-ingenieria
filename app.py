import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import tempfile, zipfile, os, xmltodict, random

# ---------- CONFIGURACIÓN ----------
st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📡 Dashboard Ingeniería FTTH")
st.markdown("Subí tu archivo `.kmz`, `.kml` o `.rtf` para visualizar el plano de ingeniería FTTH.")

uploaded_file = st.file_uploader("📁 Subir archivo", type=["kmz", "kml", "rtf"])

# ---------- EXTRACCIÓN DEL KML ----------
def extract_kml(uploaded_file):
    """Extrae el texto KML desde KMZ, KML o RTF."""
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

# ---------- PARSEO DEL KML ----------
def parse_kml(kml_path):
    """Lee el KML y clasifica coordenadas por capa, tolerando estructuras anidadas."""
    with open(kml_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        kml_dict = xmltodict.parse(content)
    except Exception:
        st.error("No se pudo interpretar el KML. Verificá que esté bien formado.")
        return {k: [] for k in ["TRONCALES", "DERIVACION", "PRECON", "HUB", "NAP", "FOSC", "NODOS"]}

    capas = {k: [] for k in ["TRONCALES", "DERIVACION", "PRECON", "HUB", "NAP", "FOSC", "NODOS"]}

    def buscar_placemarks(nodo, carpeta_actual=""):
        if isinstance(nodo, dict):
            for key, value in nodo.items():
                if key == "Folder":
                    folders = value if isinstance(value, list) else [value]
                    for f in folders:
                        nombre = str(f.get("name", "")).upper()
                        buscar_placemarks(f, carpeta_actual=nombre)
                elif key == "Placemark":
                    placemarks = value if isinstance(value, list) else [value]
                    for p in placemarks:
                        tipo = carpeta_actual.upper()
                        coords_text = None

                        if isinstance(p, dict):
                            if "LineString" in p and "coordinates" in p["LineString"]:
                                coords_text = p["LineString"]["coordinates"]
                            elif "Point" in p and "coordinates" in p["Point"]:
                                coords_text = p["Point"]["coordinates"]

                        if coords_text:
                            try:
                                coords = [list(map(float, c.split(",")[:2])) for c in coords_text.strip().split()]
                            except Exception:
                                continue
                            tipo_key = next((k for k in capas if k in tipo), "NODOS")
                            capas[tipo_key].append(coords)

                elif isinstance(value, (dict, list)):
                    buscar_placemarks(value, carpeta_actual)

    buscar_placemarks(kml_dict)
    return capas

# ---------- PROCESAMIENTO PRINCIPAL ----------
if uploaded_file:
    kml_path = extract_kml(uploaded_file)
    if not kml_path:
        st.error("❌ No se pudo extraer el KML del archivo.")
        st.stop()

    capas = parse_kml(kml_path)

    all_coords = [pt for lista in capas.values() for seg in lista for pt in seg]
    if not all_coords:
        st.warning("⚠️ No se encontraron coordenadas válidas en el archivo.")
        st.info("Verificá que el archivo contenga carpetas con coordenadas (ej: TRONCALES, DERIVACION, NAP, HUB...).")
        st.json({k: len(v) for k, v in capas.items()})  # diagnóstico rápido
        st.stop()

    lon_center = sum(p[0] for p in all_coords) / len(all_coords)
    lat_center = sum(p[1] for p in all_coords) / len(all_coords)

    # Simular NAPs y clientes
    naps = capas["NAP"]
    clientes, potencias = [], []
    for nap in naps:
        for (x, y) in nap:
            for _ in range(random.randint(3, 8)):
                cx = x + random.uniform(-0.00025, 0.00025)
                cy = y + random.uniform(-0.00025, 0.00025)
                clientes.append([cx, cy])
                potencias.append(round(random.uniform(-25, -17), 2))

    # ---------- MÉTRICAS SUPERIORES ----------
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Troncales", len(capas["TRONCALES"]))
    c2.metric("Derivaciones", len(capas["DERIVACION"]))
    c3.metric("Preconectorizado", len(capas["PRECON"]))
    c4.metric("HUB", len(capas["HUB"]))
    c5.metric("NAP", len(capas["NAP"]))
    c6.metric("FOSC", len(capas["FOSC"]))
    c7.metric("Clientes", len(clientes))

    # ---------- MAPA ----------
    fig = go.Figure()

    colores = {
        "TRONCALES": "red",
        "DERIVACION": "green",
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

    # Puntos (HUB, NAP, FOSC, NODOS)
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
            style="carto-darkmatter",  # Fondo oscuro
            center=dict(lat=lat_center, lon=lon_center),
            zoom=13
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=700,
        legend=dict(x=0, y=1)
    )

    st.plotly_chart(fig, use_container_width=True)
