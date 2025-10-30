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

# -------------------------------
# CONFIGURACIÓN
# -------------------------------
st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📶 Dashboard Ingeniería FTTH")
st.markdown("**Visualización de red, NAPs, HUBs y clientes simulados**")

# -------------------------------
# CARGA DEL ARCHIVO KMZ/KML
# -------------------------------
uploaded_file = st.file_uploader("📂 Subí el archivo del proyecto FTTH (.KMZ o .KML)", type=["kmz", "kml"])

def leer_kmz_multi(uploaded_file):
    """Lee todas las capas del KMZ/KML (estructura FTTH simplificada)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, uploaded_file.name)
        with open(path, "wb") as f:
            f.write(uploaded_file.getvalue())

        # Si es KMZ, descomprimir
        if uploaded_file.name.endswith(".kmz"):
            with ZipFile(path, "r") as zip_ref:
                zip_ref.extractall(tmpdir)
            kml_files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".kml")]
            if not kml_files:
                st.error("❌ No se encontró ningún archivo .kml dentro del KMZ.")
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
        else:
            return None

# -------------------------------
# MAPA BASE
# -------------------------------
map_fig = go.Figure()

if uploaded_file:
    gdf = leer_kmz_multi(uploaded_file)
    if gdf is not None and not gdf.empty:
        st.success(f"✅ Archivo {uploaded_file.name} cargado correctamente")

        # Filtrar capas por nombre
        capas = gdf["layer"].unique()
        st.write("Capas detectadas:", list(capas))

        # Definir colores
        colores = {
            "TRONCAL": "red",
            "DERIV": "green",
            "PRECO": "violet"
        }

        # Variables para centrar el mapa
        all_lat, all_lon = [], []

        # Dibujar líneas
        for tipo in ["TRONCAL", "DERIV", "PRECO"]:
            subset = gdf[gdf["layer"].str.contains(tipo)]
            for _, row in subset.iterrows():
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue
                if geom.geom_type == "LineString":
                    lon, lat = geom.xy
                    all_lat.extend(lat)
                    all_lon.extend(lon)
                    map_fig.add_trace(go.Scattermapbox(
                        lon=lon,
                        lat=lat,
                        mode="lines",
                        line=dict(width=3, color=colores.get(tipo, "gray")),
                        name=tipo
                    ))
                elif geom.geom_type == "MultiLineString":
                    for g in geom.geoms:
                        lon, lat = g.xy
                        all_lat.extend(lat)
                        all_lon.extend(lon)
                        map_fig.add_trace(go.Scattermapbox(
                            lon=lon, lat=lat, mode="lines",
                            line=dict(width=3, color=colores.get(tipo, "gray")),
                            name=tipo
                        ))

        # Dibujar puntos HUB, NAP, FOSC, NODOS
        puntos = []
        for tipo in ["HUB", "NAP", "FOSC", "NODOS"]:
            subset = gdf[gdf["layer"].str.contains(tipo)]
            if subset.empty:
                continue
            subset["lon"] = subset.geometry.x
            subset["lat"] = subset.geometry.y
            all_lat.extend(subset["lat"])
            all_lon.extend(subset["lon"])

            icon_url = None
            size = 12
            color = "gray"

            if tipo == "HUB":
                icon_url = "http://maps.google.com/mapfiles/kml/shapes/polygon.png"
                color = "blue"
            elif tipo == "NAP":
                icon_url = "http://maps.google.com/mapfiles/kml/shapes/triangle.png"
                color = "red"
            elif tipo == "FOSC":
                color = "black"
                size = 10
            elif tipo == "NODOS":
                color = "yellow"
                size = 14

            map_fig.add_trace(go.Scattermapbox(
                lat=subset["lat"],
                lon=subset["lon"],
                mode="markers",
                marker=dict(size=size, color=color),
                name=tipo,
                text=subset["Name"] if "Name" in subset.columns else tipo
            ))

            if tipo == "NAP":
                puntos = subset[["lat", "lon"]].to_numpy()

        # Simular clientes alrededor de NAPs
        clientes = []
        for lat, lon in puntos:
            for _ in range(np.random.randint(3, 8)):
                clientes.append({
                    "lat": lat + np.random.uniform(-0.0005, 0.0005),
                    "lon": lon + np.random.uniform(-0.0005, 0.0005),
                    "potencia": np.round(np.random.uniform(-25, -17), 2)
                })
        if clientes:
            df_clientes = pd.DataFrame(clientes)
            map_fig.add_trace(go.Scattermapbox(
                lat=df_clientes["lat"],
                lon=df_clientes["lon"],
                mode="markers",
                marker=dict(size=5, color="lightgray", opacity=0.6),
                name="Clientes simulados",
                text=df_clientes["potencia"].astype(str) + " dBm"
            ))

        # Centrar mapa
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
        st.warning("⚠️ No se encontraron geometrías válidas en el archivo.")
else:
    st.info("Subí un archivo KMZ o KML para ver el tendido FTTH.")
