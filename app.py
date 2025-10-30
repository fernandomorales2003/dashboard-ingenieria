# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import geopandas as gpd
from zipfile import ZipFile
import tempfile
import os
import fiona
from shapely.geometry import LineString, MultiLineString, GeometryCollection

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📶 Dashboard Ingeniería FTTH")
st.markdown("**Visualización del tendido, HUB, NAP, FOSC, NODOS y clientes simulados**")

# -------------------------------
# FUNCIONES
# -------------------------------
def leer_kmz(uploaded_file):
    """Lee todas las capas de un KMZ/KML, incluyendo geometrías complejas."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, uploaded_file.name)
        with open(path, "wb") as f:
            f.write(uploaded_file.getvalue())

        if uploaded_file.name.endswith(".kmz"):
            with ZipFile(path, "r") as zip_ref:
                zip_ref.extractall(tmpdir)
            kml_files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".kml")]
            if not kml_files:
                return None
            path = kml_files[0]

        all_layers = []
        for layer in fiona.listlayers(path):
            try:
                gdf = gpd.read_file(path, driver="KML", layer=layer)
                if not gdf.empty:
                    gdf["layer"] = layer.upper()
                    all_layers.append(gdf)
            except Exception:
                continue
        if all_layers:
            return pd.concat(all_layers, ignore_index=True)
        return None


def extraer_lineas(geom):
    """Devuelve una lista de LineString válidas desde geometrías mixtas."""
    lineas = []
    if geom is None or geom.is_empty:
        return lineas
    try:
        if isinstance(geom, LineString):
            lineas.append(geom)
        elif isinstance(geom, MultiLineString):
            lineas.extend(list(geom.geoms))
        elif isinstance(geom, GeometryCollection):
            for g in geom.geoms:
                lineas.extend(extraer_lineas(g))
    except Exception:
        pass
    return lineas


# -------------------------------
# APP
# -------------------------------
uploaded_file = st.file_uploader("📂 Subí el archivo FTTH (.KMZ o .KML)", type=["kmz", "kml"])

if uploaded_file:
    gdf = leer_kmz(uploaded_file)
    if gdf is None or gdf.empty:
        st.error("❌ No se encontraron geometrías válidas.")
        st.stop()

    st.success(f"✅ Archivo {uploaded_file.name} cargado correctamente.")
    capas = gdf["layer"].unique()
    st.write("Capas detectadas:", list(capas))

    map_fig = go.Figure()
    all_lat, all_lon = [], []

    # Colores definidos
    color_lineas = {"TRONCAL": "red", "DERIV": "green", "PRECO": "violet"}
    color_puntos = {
        "HUB": "blue",
        "NAP": "red",
        "FOSC": "black",
        "NODOS": "yellow"
    }

    # --- DIBUJAR LÍNEAS ---
    for tipo in ["TRONCAL", "DERIV", "PRECO"]:
        subset = gdf[gdf["layer"].str.contains(tipo, case=False, na=False)]
        if subset.empty:
            continue
        for _, row in subset.iterrows():
            geoms = extraer_lineas(row.geometry)
            for g in geoms:
                try:
                    lon, lat = g.xy
                    if len(lat) == 0 or len(lon) == 0:
                        continue
                    all_lat.extend(lat)
                    all_lon.extend(lon)
                    map_fig.add_trace(go.Scattermapbox(
                        lon=lon, lat=lat, mode="lines",
                        line=dict(width=3, color=color_lineas.get(tipo, "gray")),
                        name=tipo
                    ))
                except Exception:
                    continue

    # --- DIBUJAR PUNTOS ---
    nap_coords = []
    for tipo in ["HUB", "NAP", "FOSC", "NODOS"]:
        subset = gdf[gdf["layer"].str.contains(tipo, case=False, na=False)]
        if subset.empty:
            continue
        try:
            subset["lon"] = subset.geometry.x
            subset["lat"] = subset.geometry.y
        except Exception:
            continue
        subset = subset.dropna(subset=["lat", "lon"])
        if subset.empty:
            continue
        all_lat.extend(subset["lat"])
        all_lon.extend(subset["lon"])
        map_fig.add_trace(go.Scattermapbox(
            lat=subset["lat"],
            lon=subset["lon"],
            mode="markers",
            marker=dict(size=12, color=color_puntos[tipo]),
            name=tipo
        ))
        if tipo == "NAP":
            nap_coords = subset[["lat", "lon"]].to_numpy()

    # --- CLIENTES SIMULADOS ---
    if len(nap_coords) > 0:
        clientes = []
        for lat, lon in nap_coords:
            for _ in range(np.random.randint(3, 8)):
                clientes.append({
                    "lat": lat + np.random.uniform(-0.0005, 0.0005),
                    "lon": lon + np.random.uniform(-0.0005, 0.0005),
                    "potencia": np.round(np.random.uniform(-25, -17), 2)
                })
        clientes_df = pd.DataFrame(clientes)
        map_fig.add_trace(go.Scattermapbox(
            lat=clientes_df["lat"],
            lon=clientes_df["lon"],
            mode="markers",
            marker=dict(size=5, color="lightgray", opacity=0.7),
            text=clientes_df["potencia"].astype(str) + " dBm",
            name="Clientes simulados"
        ))

    # --- CENTRAR MAPA ---
    if all_lat and all_lon:
        map_fig.update_layout(
            mapbox=dict(
                center=dict(lat=np.mean(all_lat), lon=np.mean(all_lon)),
                zoom=14,
                style="carto-positron"
            ),
            margin={"r":0,"t":0,"l":0,"b":0}
        )

    st.plotly_chart(map_fig, use_container_width=True)
else:
    st.info("Subí un archivo KMZ/KML con estructura FTTH (TRONCAL, DERIV, PRECO, HUB, NAP, FOSC, NODOS).")
