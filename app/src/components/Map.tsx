import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Tooltip } from 'react-leaflet';
import { renderToString } from 'react-dom/server';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBriefcaseMedical } from '@fortawesome/free-solid-svg-icons';

const hospitalHtmlIcon = L.divIcon({
    className: 'custom-fa-marker',
    html: renderToString(
        <div className="flex items-center justify-center w-20 h-20">
            <FontAwesomeIcon
                icon={faBriefcaseMedical}
                style={{ color: '#e65a84' }}
                className="text-xl"
            />
        </div>
    ),
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -16]
});


interface HealthUnit {
    type: string;
    geometry: {
        type: string;
        coordinates: [number, number]; // [longitude, latitude]
    };
    properties: {
        name: string;
        amenity: string;
    };
}

export default function Map() {
    const API_ADDRESS = import.meta.env.VITE_API_ADDRESS;
    const center: [number, number] = [14.1797, 121.2431];
    const lagunaBounds = L.latLngBounds([13.9635, 121.0053], [14.5958, 121.6346]);

    const [units, setUnits] = useState<HealthUnit[]>([]);

    useEffect(() => {
        async function fetchHealthUnits() {
            try {
                const response = await fetch(`${API_ADDRESS}/health-units`);
                const data = await response.json();
                if (data && data.features) {
                    setUnits(data.features);
                }
            } catch (error) {
                console.error("Error fetching units:", error);
            }
        }
        fetchHealthUnits();
    }, [API_ADDRESS]);

    return (
        <div className="flex-1 w-max">
            <MapContainer 
                center={center}
                zoom={13} 
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

                {units.map((unit, index) => {
                    const [lng, lat] = unit.geometry.coordinates;
                    const position: [number, number] = [lat, lng];

                    return (
                        <Marker key={index} position={position} icon={hospitalHtmlIcon}>
                            <Tooltip
                                direction="top"
                                offset={[-8, -12]}
                                className="glass-tooltip"
                            >
                                <div>
                                    <span className="font-bold">
                                        {unit.properties.name}
                                    </span>
                                </div>
                            </Tooltip>
                        </Marker>
                    );
                })}
            </MapContainer>
        </div>
    );
}