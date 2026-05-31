import streamlit as st
import requests
import math
from datetime import datetime
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title='Nearest Transit Stop Finder', layout='wide')

OVERPASS_URL = 'https://overpass-api.de/api/interpreter'
IPINFO_URL = 'https://ipinfo.io/json'

# ---------------- Helpers ---------------- #
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

@st.cache_data(ttl=300)
def get_ip_location():
    r = requests.get(IPINFO_URL, timeout=10)
    r.raise_for_status()
    data = r.json()
    loc = data.get('loc', '0,0').split(',')
    return float(loc[0]), float(loc[1]), data.get('city', ''), data.get('country', '')

@st.cache_data(ttl=300)
def get_nearby_stops(lat, lon, radius=800):
    query = f"""
    [out:json][timeout:25];
    (
      node["highway"="bus_stop"](around:{radius},{lat},{lon});
      node["public_transport"="platform"](around:{radius},{lat},{lon});
      node["railway"="tram_stop"](around:{radius},{lat},{lon});
      node["station"="light_rail"](around:{radius},{lat},{lon});
    );
    out body;
    """
    headers = {
        "User-Agent": "NearestTransitApp/1.0 (Streamlit Python App)",
        "Accept-Language": "en"
    }
    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data=query,
        headers=headers,
        timeout=30
    )
    response.raise_for_status()
    return response.json().get("elements", [])


def classify(tags):
    if tags.get('railway') == 'tram_stop':
        return 'Tram'
    if tags.get('highway') == 'bus_stop':
        return 'Bus'
    return 'Transit'

# ---------------- UI ---------------- #
st.title('Nearest Tram / Bus Stop Finder')
st.write('Find nearby public transport stops using your current location.')

st.subheader("Choose Location Source")

mode = st.radio(
    "Location Method",
    ["Use Browser GPS (Recommended)", "Use IP Location", "Manual Coordinates"]
)

lat = lon = None

if mode == "Use Browser GPS (Recommended)":

    location = streamlit_geolocation()

    if location and location["latitude"]:
        lat = location["latitude"]
        lon = location["longitude"]

        st.session_state["lat"] = lat
        st.session_state["lon"] = lon

        st.success(f"GPS Found: {lat:.6f}, {lon:.6f}")

elif mode == "Use IP Location":

    if st.button("Detect IP Location"):

        lat, lon, city, country = get_ip_location()

        st.session_state["lat"] = lat
        st.session_state["lon"] = lon

        st.success(f"{city}, {country}")

elif mode == "Manual Coordinates":

    c1, c2 = st.columns(2)

    with c1:
        lat = st.number_input("Latitude", value=51.0504)

    with c2:
        lon = st.number_input("Longitude", value=13.7373)

    st.session_state["lat"] = lat
    st.session_state["lon"] = lon

lat = st.session_state.get('lat')
lon = st.session_state.get('lon')
radius = st.slider('Search radius (meters)', 200, 3000, 800, 100)
limit = st.slider('Max results', 3, 20, 10)

if lat is not None and lon is not None:
    if st.button('Find Nearby Stops'):
        try:
            stops = get_nearby_stops(lat, lon, radius)
            rows = []
            seen = set()
            for s in stops:
                tags = s.get('tags', {})
                name = tags.get('name', 'Unnamed Stop')
                key = (name, round(s['lat'],5), round(s['lon'],5))
                if key in seen:
                    continue
                seen.add(key)
                dist = haversine(lat, lon, s['lat'], s['lon'])
                rows.append({
                    'name': name,
                    'type': classify(tags),
                    'distance_km': dist,
                    'walk_min': max(1, round(dist / 5 * 60)),
                    'lat': s['lat'],
                    'lon': s['lon']
                })
            rows = sorted(rows, key=lambda x: x['distance_km'])[:limit]
            if not rows:
                st.warning('No stops found in this radius.')
            else:
                st.subheader('Nearest Stops')
                for i, r in enumerate(rows, start=1):
                    with st.container(border=True):
                        st.markdown(f"### {i}. {r['name']}")
                        st.write(f"Type: {r['type']}")
                        st.write(f"Distance: {r['distance_km']:.2f} km")
                        st.write(f"Estimated walk: {r['walk_min']} min")
                        maps = f"https://www.google.com/maps/search/?api=1&query={r['lat']},{r['lon']}"
                        st.link_button('Open in Maps', maps)
        except Exception as e:
            st.error(f'Error searching stops: {e}')
else:
    st.info('Choose a location source and detect/set location first.')

st.caption('Data source: OpenStreetMap / Overpass API. IP geolocation is approximate.')