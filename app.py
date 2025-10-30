# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
from zipfile import ZipFile
from io import BytesIO
import tempfile
import os
import datetime

# -------------------------------
# CONFIGURACIÓN INICIAL
# -------------------------------
st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📶 Dashboard de Ingeniería FTTH")
st.markdown("**Visualización de red, NAPs y clientes - Proyecto FTTH (Demo)**")

# -------------------------------
# DATOS SIMULADOS
# -------------------------------
np.random.seed(42)
n_naps = 10
naps = [f"NAP-{i:02d}" for i in range(1, n_naps+1)]
clientes_por_nap = np.random.randint(6, 16, n_naps)

nap_data = pd.DataFrame({
    "NAP": naps,
    "Puertos totales": 16,
    "Puertos ocupados": clientes_por_nap,
    "Ocupación (%)": np.round((clientes_por_nap / 16) * 100, 1),
    "Potencia promedio (dBm)": np.round(np.random.uniform(-24, -18, n_naps), 2),
    "Latitud": np.random.uniform(-34.61, -34.56, n_naps),
    "Longitud": np.random.uniform(-58.45, -58.40, n_naps)
})

n_clientes = int(sum(clientes_por_nap))
clientes = []
for i in range(n_clientes):
    nap = np.random.choice(naps)
    clientes.append({
        "ID Cliente": f"CL-{1000+i}",
        "NAP asignada": nap,
        "Dirección": f"Calle {np.random.randint(1, 2000)}",
        "Fecha de alta": datetime.date(2025, np.random.randint(1, 10), np.random.randint(1, 28)),
        "Potencia (dBm)": np.round(np.random.uniform(-27, -15), 2),
        "Estado": np.random.choice(["Activo", "Pendiente", "Baja"], p=[0.8, 0.15, 0.05])
    })
clientes_df = pd.DataFrame(clientes)

# -------------------------------
# SECCIÓN 1 - RESUMEN GENERAL
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
st.subheader("🗺️ Mapa de tendido y NAPs")

uploaded_file = st.file_uploader("📂 Subí el archivo del tendido (.KMZ o .KML)", type=["kmz", "kml"])

# Función auxiliar para leer KMZ o KML
def leer_kmz(uploaded_file):
    with tempfile.TemporaryDirectory() as tmpdir:
        kmz_path = os.path.join(tmpdir, "tendido.kmz")
        with open(kmz_path, "wb") as f:
            f.write(uploaded_file.getvalue())

        # Descomprimir si es KMZ
        with ZipFile(kmz_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)
        kml_files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".kml")]
        if not kml_files:
            st.error("No se encontró ningún archivo .kml dentro del KMZ.")
            return None
        gdf = gpd.read_file(kml_files[0], driver="KML")
        return gdf

# Renderización del mapa
if uploaded_file:
    if uploaded_file.name.endswith(".kmz"):
        gdf = leer_kmz(uploaded_file)
    else:
        gdf = gpd.read_file(uploaded_file, driver="KML")

    if gdf is not None and not gdf.empty:
        st.success(f"Archivo {uploaded_file.name} cargado correctamente ✅")
        # Crear figura base
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
            height=600
        )

        # Agregar líneas del KML
        for _, row in gdf.iterrows():
            if row.geometry.geom_type == "LineString":
                lon, lat = row.geometry.xy
                map_fig.add_trace(go.Scattermapbox(
                    lon=lon, lat=lat,
                    mode="lines",
                    line=dict(width=3, color="#00cc83"),
                    name="Tendido FO"
                ))

        map_fig.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(map_fig, use_container_width=True)
    else:
        st.warning("El archivo cargado no contiene geometrías válidas.")
else:
    st.info("Subí un archivo KMZ o KML para ver el trazado del tendido.")

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

st.success("✅ Dashboard interactivo listo para workshop FTTH.")
