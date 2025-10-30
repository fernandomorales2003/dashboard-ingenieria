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

# === AGRUPAMOS TODAS LAS LINEAS DE CADA TIPO ===
for tipo in ["TRONCAL", "DERIVACION", "PRECON"]:
    all_lon, all_lat = [], []
    for seg in capas[tipo]:
        if len(seg) > 1:
            lon, lat = zip(*seg)
            all_lon += [None] + list(lon)  # None separa segmentos
            all_lat += [None] + list(lat)
    if all_lon:
        fig.add_trace(go.Scattermapbox(
            lon=all_lon, lat=all_lat, mode="lines",
            line=dict(width=3, color=colores[tipo]),
            name=tipo,
            hoverinfo="none",
        ))

# === AGRUPAMOS PUNTOS ===
for tipo in ["HUB", "NAP", "FOSC", "NODOS"]:
    if capas[tipo]:
        lon = [p[0][0] for p in capas[tipo]]
        lat = [p[0][1] for p in capas[tipo]]
        fig.add_trace(go.Scattermapbox(
            lon=lon, lat=lat, mode="markers",
            marker=dict(size=10, color=colores[tipo], symbol="circle"),
            name=tipo,
            hoverinfo="none",
        ))

# === CLIENTES SIMULADOS (INICIAN OCULTOS) ===
if clientes:
    lon, lat = zip(*clientes)
    fig.add_trace(go.Scattermapbox(
        lon=lon, lat=lat, mode="markers",
        marker=dict(size=5, color="lime"),
        text=[f"{p} dBm" for p in potencias],
        name="Clientes (Simulados)",
        hoverinfo="text",
        visible="legendonly",  # 🔹 Ocultos por defecto
    ))

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
