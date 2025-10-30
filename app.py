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

# --------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------
st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📶 Dashboard Ingeniería FTTH")
st.markdown("**Visualización de red, NAPs, HUBs, FOSC, NODOS y clientes simulados**")

# --------------------------------------------
# CARGA KMZ/KML
# --------------------------------------------
uploaded_file = st.file_uploader("📂 Subí el archivo del proyecto FTTH (.KMZ o .KML)", type=["kmz", "kml"])

def leer_kmz(uploaded_file):
    """Lee todas las capas de un KMZ/KML y devuelve un GeoDataFrame combinado."""
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

# --------------------------------------------
# MAPA
# --------------------------------------------
if uploaded_file:
    gdf = leer_kmz(uploaded_file)
    if gdf is None or gdf.empty:
        st.error("❌ No se encontraron geometrías válidas en el archivo.")
        st.stop()

    st.success(f"✅ Archivo {uploaded_file.name} cargado correctamente")

    capas = gdf["layer"].unique()
    st.write("Capas detectadas:", list(capas))

    map_fig = go.Figure()
    all_lat, all_lon = [], []

    # Colores por tipo
    colores = {"TRONCAL": "red", "DERIV": "green", "PRECO": "violet"}

    # --- LINEAS ---
    for tipo in ["TRONCAL", "DERIV", "PRECO"]:
        subset = gdf[gdf["layer"].str.contains(tipo)]
        if subset.empty:
            continue
        for _, row in subset.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            if geom.geom_type == "LineString":
                lon, lat = geom.xy
                if len(lat) == 0 or len(lon) == 0:
                    continue
                all_lat.extend(lat)
                all_lon.extend(lon)
                map_fig.add_trace(go.Scattermapbox(
                    lon=lon, lat=lat, mode="lines",
                    line=dict(width=3, color=colores[tipo]),
                    name=tipo
                ))
            elif geom.geom_type == "MultiLineString":
                for g in geom.geoms:
                    lon, lat = g.xy
                    if len(lat) == 0 or len(lon) == 0:
                        continue
                    all_lat.extend(lat)
                    all_lon.extend(lon)
                    map_fig.add_trace(go.Scattermapbox(
                        lon=lon, lat=lat, mode="lines",
                        line=dict(width=3, color=colores[tipo]),
                        name=tipo
                    ))

    # --- PUNTOS ---
    nap_coords = []
    iconos = {
        "HUB": {"color": "blue", "size": 12},
        "NAP": {"color": "red", "size": 12},
        "FOSC": {"color": "black", "size": 10},
        "NODOS": {"color": "yellow", "size": 14}
    }

    for tipo in ["HUB", "NAP", "FOSC", "NODOS"]:
        subset = gdf[gdf["layer"].str.contains(tipo)]
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
            marker=dict(size=iconos[tipo]["size"], color=iconos[tipo]["color"]),
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
    st.info("Subí un archivo KMZ o KML con estructura FTTH para visualizar.")
