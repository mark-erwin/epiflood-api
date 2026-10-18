import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
// Fix for missing default marker icons in Leaflet when using bundlers
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
import L from 'leaflet';


let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

export default function Map() {
  // Example coordinates (e.g., London)
    const position: [number, number] = [51.505, -0.09];
    const lagunaBounds: [[number, number], [number, number]] = [
        [13.85, 121.00], // Southwest corner (near Batangas/Quezon border)
        [14.55, 121.65]  // Northeast corner (near Rizal/Quezon border)
    ];

  return (
    <div style={{ flex: 1, width: '100%' }}>

        <MapContainer 
            center={[14.1797, 121.2431]}
            zoom={11} 
            minZoom={12}
            maxBounds={lagunaBounds}
            maxBoundsViscosity={1.0}
            style={{ height: '100vh', width: '100vw' }}
            >
            <TileLayer
            url="https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles style by <a href="https://www.hotosm.org/">HOT</a>'
            />
        <Marker position={position}>
            <Popup>
            A pretty CSS popup. <br /> Easily customizable.
            </Popup>
        </Marker>
        </MapContainer>
    </div>

  );
}
