import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
// Fix for missing default marker icons in Leaflet when using bundlers
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
import L from 'leaflet';


patchMapTileGapBug();
function patchMapTileGapBug() {
    const proto = L.GridLayer.prototype as any;
    
    let originalInitTile = proto._initTile;
    if (!originalInitTile || originalInitTile.isPatched) return;

    L.GridLayer.include({
        _initTile: function (tile: HTMLElement) {
            originalInitTile.call(this, tile);

            var tileSize = this.getTileSize();

            tile.style.width = tileSize.x + 1 + 'px';
            tile.style.height = tileSize.y + 1 + 'px';
        }
    });

    proto._initTile.isPatched = true;
}

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
        <Marker position={position}>
            <Popup>
            A pretty CSS popup. <br /> Easily customizable.
            </Popup>
        </Marker>
        </MapContainer>
    </div>
  );
}
