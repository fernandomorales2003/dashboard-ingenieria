# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import datetime

# -------------------------------
# CONFIGURACIÓN INICIAL
# -------------------------------
st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📶 Dashboard de Ingeniería FTTH")
st.markdown("**Panel de control del proyecto de red óptica FTTH - Datos simulados**")

# -------------------------------
# GENERACIÓN DE DATOS FICTICIOS
# -------------------------------
np.random.seed(42)

# Simulación de NAPs
n_naps = 10
naps = [f"NAP-{i:02d}" for i in range(1, n_naps+1)]
ocupacion = np.random.randint(40, 100, n_naps)
clientes_por_nap = ocupacion // 4

nap_data = pd.DataFrame({
    "NAP": naps,
    "Puertos totales": 16,
    "Puertos ocupados": clientes_por_nap,
    "Ocupación (%)": np.round((clientes_por_nap / 16) * 100, 1),
    "Potencia promedio (dBm)": np.round(np.random.uniform(-24, -18, n_naps), 2),
    "Latitud": np.random.uniform(-34.6, -34.55, n_naps),
    "Longitud": np.random.uniform(-58.45, -58.40, n_naps)
})

# Simulación de clientes
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
# SECCIÓN 2 - MAPA DE LA RED
# -------------------------------
st.subheader("🗺️ Mapa de NAPs y cobertura")
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
    height=500
)
map_fig.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(map_fig, use_container_width=True)

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
# SECCIÓN 5 - EXPORTACIÓN
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

st.success("✅ Dashboard generado con datos ficticios para presentación del workshop.")
