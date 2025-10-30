# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
from zipfile import ZipFile
import tempfile
import os
import datetime
import fiona

# -------------------------------
# CONFIGURACIÓN INICIAL
# -------------------------------
st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📶 Dashboard de Ingeniería FTTH")
st.markdown("**Visualización del proyecto, NAPs y clientes - Demo interactiva**")

# -------------------------------
# DATOS SIMULADOS
# -------------------------------
np.random.seed(42)
n_naps = 10
naps = [f"NAP-{i:02d}" for i in range(1, n_naps + 1)]
clientes_por_nap = np.random.randint(8, 14, n_naps)

nap_data = pd.DataFrame({
    "NAP": naps,
    "Puertos totales": 16,
    "Puertos ocupados": clientes_por_nap,
    "Ocupación (%)": np.round((clientes_por_nap / 16) * 100, 1),
    "Potencia promedio (dBm)": np.round(np.random.uniform(-24, -18, n_naps), 2),
    "Latitud": np.random.uniform(-34.61, -34.56, n_naps),
    "Longitud": np.random.uniform(-58.45, -58.40, n_naps)
})

# CLIENTES alrededor de NAPs
clientes = []
for _, nap in nap_data.iterrows():
    for i in range(int(nap["Puertos ocupados"])):
        clientes.append({
            "ID Cliente": f"{nap['NAP']}-CL-{i+1:03d}",
            "NAP asignada": nap["NAP"],
            "Latitud": nap["Latitud"] + np.random.uniform(-0.0008, 0.0008),
            "Longitud": nap["Longitud"] + np.random.uniform(-0.0008, 0.0008),
            "Potencia (dBm)": np.round(np.random.uniform(-27, -15), 2),
            "Estado": np.random.choice(["Activo", "Pendiente", "Baja"], p=[0.8, 0.15, 0.05]),
            "Dirección": f"Calle {np.random.randint(1, 2000)}",
            "Fecha de alta": datetime.date(2025, np.random.randint(1, 10), np.random.randint(1, 28))
        })
clientes_df = pd.DataFrame(clientes)

# -------------------------------
# SECCIÓN 1 - RESUMEN
# -------------------------------
st.header("📊 Resumen del Proyecto")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("NAPs instaladas", len(naps))
col2.metric("Clientes totales", len(clientes_df))
col3.metric("Ocupación promedio", f"{nap_data['Ocupación (%)'].mean():.1f}%")
col4.metric("Potencia promedio", f"{nap_data['Potencia promedio (dBm)'].mean():.1f} dBm")
col5.metric("Red desplegada", f"{np.random.randint(12, 18)} km")

st.divider()

# -------------------------------
# SECCIÓN 2 - MAPA INTERACTIVO
# -------------------------------
st.subheader("🗺️ Mapa de tendido, NAPs y clientes")

uploaded_file = st.file_uploader("📂 Subí el archivo del tendido (.KMZ o .KML)", type=["kmz", "kml"])

def leer_kmz_multi(uploaded_file):
    """Lee todas las capas de un KMZ/KML y devuelve un GeoDataFrame combinado"""
    with tempfile.TemporaryDirectory() as tmpdir:
        kmz_path = os.path.join(tmpdir, "tendido.kmz")
        with open(kmz_path, "wb") as f:
            f.write(uploaded_file.getvalue())

        # Descomprimir KMZ
        with ZipFile(kmz_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)
        kml_files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".kml")]
        if not kml_files:
            st.error("No se encontró ningún archivo .kml dentro del KMZ.")
            return None

        all_layers = []
        # leer todas las capas dentro del KML
        for layer_name in fiona.listlayers(kml_files[0]):
            try:
                gdf_layer = gpd.read_file(kml_files[0], driver="KML", layer=layer_name)
                if not gdf_layer.empty:
                    all_layers.append(gdf_layer)
            except Exception as e:
                print(f"No se pudo leer la capa {layer_name}: {e}")

        if all_layers:
            return pd.concat(all_layers, ignore_index=True)
        else:
            return None

# --- MAPA BASE ---
map_fig = px.scatter_mapbox(
    nap_data,
    lat="Latitud",
    lon="Longitud",
    color="Ocupación (%)",
    size="Puertos ocupados",
    hover_name="NAP",
    hover_data=["Puertos totales", "Puertos ocupados", "Potencia promedio (dBm)"],
    color_continuous_scale=px.colors.sequential.Viridis,
    zoom=13,
    height=650
)

# --- CLIENTES ---
map_fig.add_trace(go.Scattermapbox(
    lat=clientes_df["Latitud"],
    lon=clientes_df["Longitud"],
    mode="markers",
    marker=go.scattermapbox.Marker(size=6, color="#2a8bf2", opacity=0.6),
    name="Clientes",
    text=clientes_df["NAP asignada"]
))

# --- TENDIDO ---
if uploaded_file:
    gdf = leer_kmz_multi(uploaded_file)
    if gdf is not None and not gdf.empty:
        st.success(f"Archivo {uploaded_file.name} cargado correctamente ✅")

        all_lines = []
        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom is None:
                continue
            if geom.geom_type == "LineString":
                all_lines.append(geom)
            elif geom.geom_type == "MultiLineString":
                all_lines.extend(list(geom.geoms))
            elif geom.geom_type == "GeometryCollection":
                for g in geom.geoms:
                    if g.geom_type == "LineString":
                        all_lines.append(g)

        if all_lines:
            for line in all_lines:
                lon, lat = line.xy
                map_fig.add_trace(go.Scattermapbox(
                    lon=lon,
                    lat=lat,
                    mode="lines",
                    line=dict(width=3, color="#00cc83"),
                    name="Tendido FO"
                ))
        else:
            st.warning("⚠️ No se detectaron líneas válidas en ninguna capa del archivo.")
    else:
        st.warning("⚠️ No se encontraron geometrías en el archivo.")
else:
    st.info("Subí un archivo KMZ o KML para ver el trazado real del tendido.")

map_fig.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(map_fig, use_container_width=True)

st.divider()

# -------------------------------
# SECCIÓN 3 - CLIENTES
# -------------------------------
st.subheader("👥 Clientes conectados")

with st.expander("Ver / cargar clientes"):
    st.dataframe(clientes_df, use_container_width=True)
    st.markdown("### ➕ Agregar nuevo cliente")
    with st.form("nuevo_cliente_form"):
        id_cliente = st.text_input("ID Cliente")
        nap_select = st.selectbox("NAP asignada", naps)
        direccion = st.text_input("Dirección")
        potencia = st.number_input("Potencia medida (dBm)", -35.0, -10.0, -22.0)
        estado = st.selectbox("Estado", ["Activo", "Pendiente", "Baja"])
        submitted = st.form_submit_button("Agregar")
        if submitted:
            st.success(f"Cliente {id_cliente or '(sin ID)'} agregado correctamente a {nap_select} ✅")

st.divider()

# -------------------------------
# SECCIÓN 4 - MÉTRICAS
# -------------------------------
st.subheader("📈 Métricas de rendimiento")

colA, colB = st.columns(2)
with colA:
    fig_ocupacion = px.bar(
        nap_data, x="NAP", y="Ocupación (%)", color="Ocupación (%)",
        text="Ocupación (%)", color_continuous_scale="Blues"
    )
    fig_ocupacion.update_layout(title="Ocupación por NAP", yaxis_title="%", xaxis_title=None)
    st.plotly_chart(fig_ocupacion, use_container_width=True)

with colB:
    fig_potencia = px.box(
        clientes_df, x="NAP asignada", y="Potencia (dBm)", color="NAP asignada",
        points="all", title="Distribución de potencia óptica por NAP"
    )
    st.plotly_chart(fig_potencia, use_container_width=True)

# -------------------------------
# EXPORTACIÓN
# -------------------------------
st.divider()
st.subheader("📤 Exportar datos")
colx, coly = st.columns(2)
with colx:
    st.download_button(
        "Descargar clientes (CSV)",
        clientes_df.to_csv(index=False).encode("utf-8"),
        "clientes_ftth.csv",
        "text/csv"
    )
with coly:
    st.download_button(
        "Descargar NAPs (CSV)",
        nap_data.to_csv(index=False).encode("utf-8"),
        "naps_ftth.csv",
        "text/csv"
    )

st.success("✅ Dashboard FTTH listo para presentación del workshop.")
