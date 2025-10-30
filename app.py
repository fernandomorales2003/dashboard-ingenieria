import streamlit as st
import plotly.graph_objects as go
import pandas as pd
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
            txt = f.read()
        ini, fin = txt.find("<kml"), txt.rfind("</kml>")
        if ini != -1 and fin != -1:
            new = path + ".kml"
            with open(new, "w", encoding="utf-8") as f:
                f.write(txt[ini:fin+6])
            return new
    return None


# ----------- PARSEO ----------
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


# ----------- APP PRINCIPAL ----------
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

    # ---- SIMULACIÓN DE CLIENTES ----
    hubs = [h["name"] for h in capas["HUB"]] if capas["HUB"] else ["HUB 1"]
    naps = [n["name"] for n in capas["NAP"]] if capas["NAP"] else ["NAP 1"]

    clientes = []
    for nap in capas["NAP"]:
        if not nap.get("coords"):
            continue
        (x, y) = nap["coords"][0]
        hub_asignado = random.choice(hubs) if hubs else "HUB 1"
        for _ in range(random.randint(4, 8)):
            cx = x + random.uniform(-0.0002, 0.0002)
            cy = y + random.uniform(-0.0002, 0.0002)
            pot = round(random.uniform(-25, -17), 2)
            clientes.append({
                "HUB": hub_asignado,
                "NAP": nap["name"],
                "x": cx,
                "y": cy,
                "Potencia (dBm)": pot
            })

    df_clientes = pd.DataFrame(clientes)

    # ---- MAPA ----
    fig = go.Figure()
    colores = {
        "TRONCAL": "red", "DERIVACION": "green", "PRECON": "violet",
        "HUB": "blue", "NAP": "magenta", "FOSC": "yellow", "NODOS": "gray"
    }

    # Líneas
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
                line=dict(width=3, color=colores.get(tipo, "white")),
                name=tipo,
                hoverinfo="skip"
            ))

    # Puntos
    for tipo in ["HUB", "NAP", "FOSC", "NODOS"]:
        puntos = capas.get(tipo, [])
        if not puntos:
            continue
        lon, lat = [], []
        for p in puntos:
            c = p.get("coords", [])
            if c:
                lon.append(c[0][0])
                lat.append(c[0][1])
        if lon and lat:
            fig.add_trace(go.Scattermapbox(
                lon=lon, lat=lat,
                mode="markers",
                marker=dict(size=8, color=colores.get(tipo, "white")),
                name=tipo,
                hoverinfo="skip"
            ))

    # Clientes
    if not df_clientes.empty:
        fig.add_trace(go.Scattermapbox(
            lon=df_clientes["x"], lat=df_clientes["y"],
            mode="markers",
            marker=dict(size=4, color="lime"),
            name="Clientes Simulados",
            visible="legendonly",
            hoverinfo="skip"
        ))

    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center=dict(lat=lat_c, lon=lon_c), zoom=12.5),
        margin=dict(l=0, r=0, t=0, b=0),
        height=720, legend=dict(x=0, y=1)
    )

    st.plotly_chart(fig, use_container_width=True)

    # ---- INDICADORES INFERIORES ----
    if not df_clientes.empty:
        st.subheader("📊 Indicadores de Clientes por HUB")

        col2, col3 = st.columns(2)

        # 📊 Columna 2 - Clientes por HUB
        with col2:
            resumen_hub = df_clientes.groupby("HUB").size().reset_index(name="Total Clientes")
            fig_bar = go.Figure(go.Bar(
                x=resumen_hub["HUB"], y=resumen_hub["Total Clientes"],
                marker_color="#00cc83"
            ))
            fig_bar.update_layout(
                title="Cantidad de Clientes por HUB",
                yaxis_title="Clientes",
                height=300
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # 📈 Columna 3 - Distribución de Potencias
        with col3:
            fig_pot = go.Figure()
            for hub in df_clientes["HUB"].unique():
                df_h = df_clientes[df_clientes["HUB"] == hub]
                fig_pot.add_trace(go.Box(
                    y=df_h["Potencia (dBm)"], name=hub,
                    boxpoints="all", jitter=0.3, whiskerwidth=0.2, marker_size=4
                ))
            fig_pot.update_layout(
                title="Distribución de Potencias por HUB",
                yaxis_title="Potencia (dBm)",
                height=300
            )
            st.plotly_chart(fig_pot, use_container_width=True)
