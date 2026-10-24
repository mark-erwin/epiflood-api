import { useEffect, useRef, useState } from 'react';
import 'ol/ol.css';
import OLMap from 'ol/Map';
import View from 'ol/View';
import TileLayer from 'ol/layer/Tile';
import XYZ from 'ol/source/XYZ';
import { fromLonLat, transformExtent } from 'ol/proj';
import FloodLayer from './FloodLayer';
import HealthUnitsLayer from './HealthUnitsLayer';
import ClustersLayer from './ClustersLayer';
import BarangayOutlinesLayer from './BarangayOutlinesLayer';

export default function Map() {
    const API_ADDRESS = import.meta.env.VITE_API_ADDRESS;
    const mapEl = useRef<HTMLDivElement>(null);
    const [map, setMap] = useState<OLMap | null>(null);

    useEffect(() => {
        if (!mapEl.current) return;

        const lagunaExtent = transformExtent(
            [121.0053, 13.9635, 121.6346, 14.5958],
            'EPSG:4326',
            'EPSG:3857'
        );

        const olMap = new OLMap({
            target: mapEl.current,
            layers: [
                     new TileLayer({
                    source: new XYZ({
                        // Carto Positron: a light, minimal basemap.
                        // Use "light_nolabels" instead of "light_all" to drop place labels entirely.
                        url: `https://{a-d}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png?key=${import.meta.env.VITE_CARTO_KEY}`,
                        maxZoom: 20,
                        attributions:
                            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, ' +
                            '&copy; <a href="https://carto.com/attributions">CARTO</a>',
                    }),
                }),
            ],
            view: new View({
                center: fromLonLat([121.2431, 14.1797]),
                zoom: 13,
                minZoom: 12,
                maxZoom: 18,
                extent: lagunaExtent,
            }),
        });

        setMap(olMap);

        return () => {
            olMap.setTarget(undefined);
            setMap(null);
        };
    }, []);

    return (
        <div className="flex-1 w-max">
            <div ref={mapEl} style={{ height: '100vh', width: '100vw' }} />
            {map && (
                <>
                    <FloodLayer map={map} api={API_ADDRESS} />
                    {/*<HealthUnitsLayer map={map} api={API_ADDRESS} />*/}
                    <ClustersLayer map={map} api={API_ADDRESS} />
                    <BarangayOutlinesLayer map={map} api={API_ADDRESS} />

                </>
            )}
        </div>
    );
}
