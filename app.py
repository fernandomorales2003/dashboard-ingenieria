import streamlit as st
import numpy as np
import pandas as pd
import pydeck as pdk
from zipfile import ZipFile
from io import BytesIO
import xml.etree.ElementTree as ET
import math

st.set_page_config(page_title="Dashboard Ingeniería FTTH", layout="wide")
st.title("📶 Dashboard Ingeniería FTTH")
st.caption("Trazas (TRONCAL/DERIV/PRECO), HUB/NAP/FOSC/NODOS y clientes simulados")

# ----------------------------
# Config
# ----------------------------
LINE_LAYERS = ["TRONCAL", "DERIV", "PRECO"]
POINT_LAYERS = ["HUB", "NAP", "FOSC", "NODOS", "NODO"]  # incluir singular

# Colores RGBA para PyDeck
LINE_COLORS = {"TRONCAL": [255, 0, 0, 200], "DERIV": [0, 180, 0, 200], "PRECO": [150, 0, 255, 200]}
POINT_COLORS = {"HUB": [0, 120, 255, 220], "NAP": [255, 0, 0, 220], "FOSC": [0, 0, 0, 220], "NODOS": [255, 200, 0, 220], "NODO": [255, 200, 0, 220]}
CLIENT_COLOR = [200, 200, 200, 180]

NS = {"kml": "http://www.opengis.net/kml/2.2", "gx": "http://www.google.com/kml/ext/2.2"}

# Mapeo de sinónimos para clasificar
def normalize_layer(name_or_path_upper: str):
    s = name_or_path_upper
    if "TRONCAL" in s or "TRONC" in s:
        return "TRONCAL"
    if "DERIVACION" in s or "DERIV." in s or "DERIV" in s:
        return "DERIV"
    if "PRECO" in s or "PRECON" in s or "PRECONEX" in s or "PRECONNEC" in s or "PRECONECTOR" in s:
        return "PRECO"
    if "HUB" in s:
        return "HUB"
    if "NAP" in s:
        return "NAP"
    if "FOSC" in s:
        return "FOSC"
    if "NODOS" in s or "NODO" in s:
        return "NODOS"
    return None

# ----------------------------
# Utilidades
# ----------------------------
def extract_kml_bytes(uploaded_file):
    raw = uploaded_file.read()
    uploaded_file.seek(0)
    if uploaded_file.name.lower().endswith(".kmz"):
        with ZipFile(BytesIO(raw)) as z:
            # prioriza doc.kml; si no, el primero que encuentre
            kml_name = next((n for n in z.namelist() if n.endswith("doc.kml")), None)
            if not kml_name:
                kml_name = next((n for n in z.namelist() if n.lower().endswith(".kml")), None)
            if not kml_name:
                return None
            return z.read(kml_name)
    return raw

def parse_coordinates_string(coord_text):
    """
    KML: "lon,lat[,alt] lon,lat[,alt] ..."
    Devuelve lista de pares [lon, lat] (orden que espera PyDeck).
    """
    coords = []
    if not coord_text:
        return coords
    for tup in coord_text.replace("\n", " ").replace("\t", " ").split():
        parts = tup.split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0]); lat = float(parts[1])
                coords.append([lon, lat])
            except Exception:
                pass
    return coords

def extract_geoms_from_placemark(pm):
    """
    Extrae todas las geometrías de un Placemark:
      - LineString -> path (lista [lon,lat])
      - Polygon (borde exterior) -> path
      - gx:Track -> path
      - Point -> punto [lon,lat]
    Devuelve lista de dicts: {"type": "line"/"point", "coords": [[lon,lat], ...]}
    """
    geoms = []

    # LineString
    for ls in pm.findall(".//{*}LineString"):
        txt = (ls.findtext(".//{*}coordinates") or "").strip()
        path = parse_coordinates_string(txt)
        if len(path) >= 2:
            geoms.append({"type": "line", "coords": path})

    # Polygon (outer boundary)
    for poly in pm.findall(".//{*}Polygon"):
        outer = poly.find(".//{*}outerBoundaryIs/{*}LinearRing/{*}coordinates")
        txt = outer.text.strip() if outer is not None and outer.text else ""
        path = parse_coordinates_string(txt)
        if len(path) >= 2:
            geoms.append({"type": "line", "coords": path})

    # gx:Track
    for tr in pm.findall(".//{"+NS["gx"]+"}Track"):
        path = []
        for c in tr.findall(".//{"+NS["gx"]+"}coord"):
            parts = (c.text or "").strip().split()
            if len(parts) >= 2:
                try:
                    lon = float(parts[0]); lat = float(parts[1])
                    path.append([lon, lat])
                except Exception:
                    pass
        if len(path) >= 2:
            geoms.append({"type": "line", "coords": path})

    # Point
    for pt in pm.findall(".//{*}Point"):
        txt = (pt.findtext(".//{*}coordinates") or "").strip()
        pts = parse_coordinates_string(txt)
        if pts:
            geoms.append({"type": "point", "coords": [pts[0]]})

    return geoms

def walk_kml(el, path_names, collector):
    """
    Recorre Document/Folder/Placemark acumulando:
      {"path": [nombres_de_carpetas], "name": nombre_placemark, "geoms": [...]}
    """
    tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
    if tag in ("Document", "Folder"):
        nm = (el.findtext("{*}name") or "").strip()
        new_path = path_names + [nm] if nm else path_names
        for child in el:
            ctag = child.tag.split("}")[-1]
            if ctag in ("Document", "Folder"):
                walk_kml(child, new_path, collector)
            elif ctag == "Placemark":
                pm_name = (child.findtext("{*}name") or "").strip()
                geoms = extract_geoms_from_placemark(child)
                if geoms:
                    collector.append({"path": new_path, "name": pm_name, "geoms": geoms})
    elif tag == "Placemark":
        pm_name = (el.findtext("{*}name") or "").strip()
        geoms = extract_geoms_from_placemark(el)
        if geoms:
            collector.append({"path": path_names, "name": pm_name, "geoms": geoms})

def classify_rec(rec):
    # Usa nombres de carpeta y del placemark para decidir capa
    upper = " / ".join([*(p or "" for p in rec["path"]), rec["name"]]).upper()
    return normalize_layer(upper)

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    φ1, λ1, φ2, λ2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dφ = φ2 - φ1
    dλ = λ2 - λ1
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def path_length_km(path_lonlat):
    if len(path_lonlat) < 2:
        return 0.0
    total = 0.0
    for i in range(len(path_lonlat)-1):
        lon1, lat1 = path_lonlat[i]
        lon2, lat2 = path_lonlat[i+1]
        total += haversine_m(lat1, lon1, lat2, lon2)
    return total / 1000.0

# ----------------------------
# App
# ----------------------------
uploaded = st.file_uploader("📂 Subí tu archivo FTTH (.KMZ / .KML)", type=["kmz", "kml"])

if uploaded:
    kml_bytes = extract_kml_bytes(uploaded)
    if not kml_bytes:
        st.error("❌ No se pudo leer el KML dentro del archivo.")
        st.stop()

    try:
        root = ET.fromstring(kml_bytes)
    except Exception as e:
        st.error(f"❌ Error al parsear el XML: {e}")
        st.stop()

    # Recolectar placemarks
    recs = []
    walk_kml(root, [], recs)

    # Clasificar y separar paths/puntos
    # Para líneas usamos PathLayer con 'path' = [[lon,lat], ...]
    path_rows = []  # dict(layer,color,path)
    point_rows = [] # dict(layer,color,lon,lat)
    path_count = {"TRONCAL":0, "DERIV":0, "PRECO":0}
    point_count = {"HUB":0, "NAP":0, "FOSC":0, "NODOS":0}

    for rec in recs:
        layer = classify_rec(rec)
        if not layer:
            continue
        for g in rec["geoms"]:
            if g["type"] == "line" and layer in LINE_COLORS:
                # normalizar: eliminar duplicados consecutivos
                path = []
                prev = None
                for pt in g["coords"]:
                    if prev is None or pt != prev:
                        path.append(pt)
                        prev = pt
                if len(path) >= 2:
                    path_rows.append({"layer": layer, "color": LINE_COLORS[layer], "path": path})
                    path_count[layer] += 1
            elif g["type"] == "point" and (layer in POINT_COLORS or layer == "NODO"):
                # mapear NODO a NODOS
                mapped = "NODOS" if layer == "NODO" else layer
                lon, lat = g["coords"][0]
                point_rows.append({"layer": mapped, "color": POINT_COLORS[mapped], "lon": lon, "lat": lat})
                if mapped in point_count:
                    point_count[mapped] += 1

    df_paths = pd.DataFrame(path_rows, columns=["layer", "color", "path"])
    df_points = pd.DataFrame(point_rows, columns=["layer", "color", "lon", "lat"])

    # ---- Clientes simulados alrededor de NAP ----
    clientes_rows = []
    if not df_points.empty and ("NAP" in df_points["layer"].unique()):
        rng = np.random.default_rng()
        naps = df_points[df_points["layer"] == "NAP"][["lat","lon"]].to_numpy()
        for lat, lon in naps:
            n = int(rng.integers(3, 8))
            dlat = rng.uniform(-0.0005, 0.0005, n)
            dlon = rng.uniform(-0.0005, 0.0005, n)
            pots = np.round(rng.uniform(-25.0, -17.0, n), 2)
            for i in range(n):
                clientes_rows.append({"lat": lat + dlat[i], "lon": lon + dlon[i], "color": CLIENT_COLOR, "pot": f"{pots[i]} dBm"})
    df_clientes = pd.DataFrame(clientes_rows, columns=["lat","lon","color","pot"])

    # ---- KPIs ----
    total_km = 0.0
    if not df_paths.empty:
        for _, r in df_paths.iterrows():
            total_km += path_length_km(r["path"])
    total_km = round(total_km, 2)
    total_troncal = int(path_count["TRONCAL"])
    total_deriv = int(path_count["DERIV"])
    total_preco = int(path_count["PRECO"])
    total_hub = int(point_count["HUB"])
    total_nap = int(point_count["NAP"])
    total_fosc = int(point_count["FOSC"])
    total_nodos = int(point_count["NODOS"])
    total_clientes = int(len(df_clientes))

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("🧵 Longitud total red", f"{total_km} km")
    c2.metric("🔴 Troncales", total_troncal)
    c3.metric("🟢 Derivaciones", total_deriv)
    c4.metric("🟣 Preconect.", total_preco)
    c5.metric("🔷 HUB", total_hub)
    c6.metric("🔺 NAP", total_nap)
    c7.metric("👥 Clientes sim.", total_clientes)
    st.divider()

    # ---- Capas PyDeck ----
    layers = []

    if not df_paths.empty:
        layers.append(pdk.Layer(
            "PathLayer",
            data=df_paths,
            get_path="path",            # lista de [lon,lat]
            get_color="color",
            width_scale=1,
            get_width=4,
            pickable=True,
        ))

    if not df_points.empty:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=df_points,
            get_position='[lon, lat]',  # lon, lat
            get_color="color",
            get_radius=8,
            pickable=True,
        ))

    if not df_clientes.empty:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=df_clientes,
            get_position='[lon, lat]',
            get_color="color",
            get_radius=4,
            pickable=True,
            get_tooltip="pot",
        ))

    # ---- Centro y zoom ----
    if not df_points.empty:
        lat_center = float(df_points["lat"].mean())
        lon_center = float(df_points["lon"].mean())
    elif not df_paths.empty:
        # promedio de todas las coordenadas de todos los paths
        all_pts = np.vstack([np.array(p) for p in df_paths["path"].tolist()])  # shape (N,2) -> [lon, lat]
        lon_center = float(all_pts[:,0].mean())
        lat_center = float(all_pts[:,1].mean())
    else:
        # fallback Mendoza aprox
        lat_center, lon_center = -32.89, -68.85

    view_state = pdk.ViewState(latitude=lat_center, longitude=lon_center, zoom=13)
    tooltip = {"html": "<b>{layer}</b>", "style": {"backgroundColor": "white"}}

    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state, tooltip=tooltip))

else:
    st.info("Subí un archivo FTTH (.KMZ / .KML) con carpetas/nombres: TRONCAL, DERIV/DERIVACION, PRECO/PRECON..., HUB, NAP, FOSC, NODO/NODOS.")
