import streamlit as st
import plotly.graph_objects as go
import tempfile, zipfile, os, xmltodict, random

st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📡 Dashboard Ingeniería FTTH")

uploaded_file = st.file_uploader("📁 Subir archivo KMZ/KML/RTF", type=["kmz", "kml", "rtf"])

# ----------- FUNCIONES -----------

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
            txt = f.read()
        ini, fin = txt.find("<kml"), txt.rfind("</kml>")
        if ini != -1 and fin != -1:
            new = path + ".kml"
            with open(new, "w", encoding="utf-8") as f:
                f.write(txt[ini:fin+6])
            return new
    return None


def parse_kml(kml_path):
    with open(kml_path, "r", encoding="utf-8") as f:
        xml = f.read()

    try:
        data = xmltodict.parse(xml)
    except Exception:
        st.error("Archivo KML inválido.")
        return {k: [] for k in ["TRONCAL", "DERIVACION", "PRECON", "HUB", "NAP", "FOSC", "NODOS"]}

    capas = {k: [] for k in ["TRONCAL", "DERIVACION", "PRECON", "HUB", "NAP", "FOSC", "NODOS"]}

    def buscar(nodo, carpeta=""):
        if isinstance(nodo, dict):
            for k, v in nodo.items():
                if k == "Folder":
                    lst = v if isinstance(v, list) else [v]
                    for f in lst:
                        buscar(f, str(f.get("name", "")).upper())
                elif k == "Placemark":
                    lst = v if isinstance(v, list) else [v]
                    for p in lst:
                        coords_txt = None
                        if "LineString" in p and "coordinates" in p["LineString"]:
                            coords_txt = p["LineString"]["coordinates"]
                        elif "Point" in p and "coordinates" in p["Point"]:
                            coords_txt = p["Point"]["coordinates"]

                        if coords_txt:
                            try:
                                coords = [list(map(float, c.split(",")[:2])) for c in coords_txt.strip().split()]
                            except Exception:
                                continue

                            tipo = "NODOS"
                            if "TRONCAL" in carpeta: tipo = "TRONCAL"
                            elif "DERIV" in carpeta: tipo = "DERIVACION"
                            elif "PRE" in carpeta: tipo = "PRECON"
                            elif "HUB" in carpeta: tipo = "HUB"
                            elif "NAP" in carpeta: tipo = "NAP"
                            elif "FOSC" in carpeta: tipo = "FOSC"
                            capas[tipo].append({"coords": coords, "name": str(p.get("name", "")).strip()})
                elif isinstance(v, (dict, list)):
                    buscar(v, carpeta)

    buscar(data)
    return capas


# ----------- MAIN -----------

if uploaded_file:
    kml = extract_kml(uploaded_file)
    if not kml:
        st.error("No se pudo procesar el archivo.")
        st.stop()

    capas = parse_kml(kml)
    coords_all = [pt for v in capas.values() for s in v for pt in s.get("coords", []) if pt]

    if not coords_all:
        st.warning("Sin coordenadas válidas.")
        st.stop()

    lon_c = sum(p[0] for p in coords_all) / len(coords_all)
    lat_c = sum(p[1] for p in coords_all) / len(coords_all)

    # ---- SIMULACIÓN CLIENTES ----
    clientes = []
    for nap in capas["NAP"]:
        for (x, y) in nap["coords"]:
            for _ in range(4):
                clientes.append((x + random.uniform(-0.0002, 0.0002),
                                 y + random.uniform(-0.0002, 0.0002)))

    # ---- MAPA ----
    fig = go.Figure()
    colores = {
        "TRONCAL": "red", "DERIVACION": "green", "PRECON": "violet",
        "HUB": "blue", "NAP": "magenta", "FOSC": "yellow", "NODOS": "gray"
    }
    simbolos = {
        "HUB": "diamond", "NAP": "triangle-up",
        "FOSC": "circle", "NODOS": "square"
    }
    tamaños = {"HUB": 16, "NAP": 13, "FOSC": 11, "NODOS": 10}

    # ---- LÍNEAS ----
    for tipo in ["TRONCAL", "DERIVACION", "PRECON"]:
        segs = capas.get(tipo, [])
        if not segs:
            continue
        lon, lat = [], []
        for s in segs:
            c = s.get("coords", [])
            if len(c) > 1:
                lons, lats = zip(*c)
                lon += [None] + list(lons)
                lat += [None] + list(lats)
        if lon and lat:
            fig.add_trace(go.Scattermapbox(
                lon=lon, lat=lat, mode="lines",
                line=dict(width=3, color=str(colores.get(tipo, "white"))),
                name=tipo
            ))

    # ---- PUNTOS ----
    for tipo in ["HUB", "NAP", "FOSC", "NODOS"]:
        puntos = capas.get(tipo, [])
        if not puntos:
            continue
        lon, lat, nombres = [], [], []
        for p in puntos:
            c = p.get("coords", [])
            if c:
                lon.append(c[0][0])
                lat.append(c[0][1])
                nombres.append(p.get("name", tipo))
        if lon and lat:
            fig.add_trace(go.Scattermapbox(
                lon=lon, lat=lat,
                mode="markers+text" if tipo == "HUB" else "markers",
                text=nombres if tipo == "HUB" else None,
                textposition="top right",
                marker=dict(
                    size=int(tamaños.get(tipo, 10)),
                    color=str(colores.get(tipo, "white")),
                    symbol=str(simbolos.get(tipo, "circle")),
                    line=dict(width=1, color="white")
                ),
                name=tipo
            ))

    # ---- CLIENTES ----
    if clientes:
        lon, lat = zip(*clientes)
        fig.add_trace(go.Scattermapbox(
            lon=lon, lat=lat, mode="markers",
            marker=dict(size=5, color="lime"),
            name="Clientes Simulados", visible="legendonly"
        ))

    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center=dict(lat=lat_c, lon=lon_c), zoom=12.5),
        margin=dict(l=0, r=0, t=0, b=0),
        height=720, legend=dict(x=0, y=1)
    )

    st.plotly_chart(fig, use_container_width=True)

