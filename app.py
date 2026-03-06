import streamlit as st
import requests
import datetime
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium

'''
# TaxiFare
'''

url = 'https://taxifare.lewagon.ai/predict'
geolocator = Nominatim(user_agent="taxifare")
st.set_page_config(page_title="TaxiFare", page_icon="🚗", layout="wide")

def geocode_address(address):
    """Convert address string to (lat, lon, full_address) or None."""
    result = geolocator.geocode(address)
    if result:
        return result.latitude, result.longitude, result.address
    return None


def get_driving_route(pickup_coords, dropoff_coords):
    """Fetch driving route from OSRM. Returns (polyline, distance_km, duration_min)."""
    lat1, lon1 = pickup_coords
    lat2, lon2 = dropoff_coords
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}"
        f"?overview=full&geometries=geojson"
    )
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("code") == "Ok":
            coords = data["routes"][0]["geometry"]["coordinates"]
            polyline = [(c[1], c[0]) for c in coords]  # OSRM gives [lon, lat]
            distance_km = data["routes"][0]["distance"] / 1000
            duration_min = data["routes"][0]["duration"] / 60
            return polyline, distance_km, duration_min
    except Exception as e:
        st.error(f"Routing error: {e}")
    return None, None, None


# --- Initialize session state ---
if "route_data" not in st.session_state:
    st.session_state.route_data = None


# --- Input fields ---
col1, col2, col3 = st.columns([3, 3, 1])

with col1:
    pickup_input = st.text_input("📍 Pickup location", placeholder="e.g. Gare du Nord, Paris")
with col2:
    dropoff_input = st.text_input("🏁 Dropoff location", placeholder="e.g. Eiffel Tower, Paris")
with col3:
    passengers = st.text_input("🏁 # passengers", placeholder="1", value=1)

_, btn_col, _ = st.columns([2, 1, 2])
with btn_col:
    search = st.button("Get Route 🗺️", type="primary")

# --- On button click: geocode + route + fare, store in session_state ---
if search:
    if not pickup_input or not dropoff_input:
        st.warning("Please fill in both pickup and dropoff locations.")
    else:
        with st.spinner("Geocoding addresses..."):
            pickup = geocode_address(pickup_input)
            dropoff = geocode_address(dropoff_input)

        if not pickup:
            st.error("❌ Pickup address not found. Try being more specific.")
        elif not dropoff:
            st.error("❌ Dropoff address not found. Try being more specific.")
        else:
            with st.spinner("Fetching driving route..."):
                route, distance, duration = get_driving_route(pickup[0:2], dropoff[0:2])

            params = {
                "pickup_datetime": datetime.datetime.now(),
                "pickup_longitude": pickup[1],
                "pickup_latitude": pickup[0],
                "dropoff_longitude": dropoff[1],
                "dropoff_latitude": dropoff[0],
                "passenger_count": passengers
            }
            try:
                r = requests.get(url, params=params)
                pred = r.json().get('fare', None)
            except Exception:
                pred = None

            # Store everything in session_state so it survives reruns
            st.session_state.route_data = {
                "pickup": pickup,
                "dropoff": dropoff,
                "route": route,
                "distance": distance,
                "duration": duration,
                "fare": pred,
            }

# --- Always render map if route_data exists in session_state ---
if st.session_state.route_data:
    data = st.session_state.route_data
    pickup   = data["pickup"]
    dropoff  = data["dropoff"]
    route    = data["route"]
    distance = data["distance"]
    duration = data["duration"]
    pred     = data["fare"]

    st.divider()

    col1, col2, col3 = st.columns(3)
    col1.metric("🛣️ Distance", f"{distance:.1f} km")
    col2.metric("⏱️ Duration", f"{int(duration)} min")
    col3.metric("💰 Predicted Fare", f"${pred:.2f}")

    # Build Folium map
    mid_lat = (pickup[0] + dropoff[0]) / 2
    mid_lon = (pickup[1] + dropoff[1]) / 2
    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=13, tiles="CartoDB positron")

    # Pickup marker (green)
    folium.Marker(
        location=pickup[0:2],
        popup=folium.Popup(pickup[2], max_width=250),
        tooltip="📍 Pickup",
        icon=folium.Icon(color="green", icon="circle", prefix="fa"),
    ).add_to(m)

    # Dropoff marker (red)
    folium.Marker(
        location=dropoff[0:2],
        popup=folium.Popup(dropoff[2], max_width=250),
        tooltip="🏁 Dropoff",
        icon=folium.Icon(color="red", icon="flag", prefix="fa"),
    ).add_to(m)

    # Route polyline
    if route:
        folium.PolyLine(
            route,
            color="#1a73e8",
            weight=5,
            opacity=0.85,
            tooltip=f"{distance:.1f} km — {int(duration)} min",
        ).add_to(m)

    # Auto-fit map bounds
    m.fit_bounds([pickup[0:2], dropoff[0:2]], padding=(40, 40))

    st_folium(m, use_container_width=True, height=520)
