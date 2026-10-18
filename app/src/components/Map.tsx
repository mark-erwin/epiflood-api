import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
// Fix for missing default marker icons in Leaflet when using bundlers
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
import L from 'leaflet';

export default function Map() {
    const center: [number, number] = [14.1797, 121.2431];
const lagunaBounds = L.latLngBounds([13.9635, 121.0053], [14.5958, 121.6346]);

  return (
    <div style={{ flex: 1, width: '100%' }}>
        <MapContainer 
            center={center}
            zoom={11} 
            maxZoom={18}
            minZoom={12}
            maxBounds={lagunaBounds}
            maxBoundsViscosity={1.0}
            style={{ height: '100vh', width: '100vw' }}
            >
        <TileLayer
        url={`https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${import.meta.env.VITE_CARTO_KEY}`}
        subdomains="abcd"
        maxZoom={20}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />
        </MapContainer>
    </div>
  );
}
