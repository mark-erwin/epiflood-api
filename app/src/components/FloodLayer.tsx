import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.vectorgrid';

const COLORS: Record<number, string> = { 1: '#facc15', 2: '#f97316', 3: '#dc2626' };

export default function FloodLayer({ api }: { api: string }) {
    const map = useMap();

    useEffect(() => {
        const layer = (L as any).vectorGrid.protobuf(
            `${api}/flood-tiles/{z}/{x}/{y}.pbf`,
            {
                rendererFactory: (L.canvas as any).tile,
                vectorTileLayerStyles: {
                    flood: (p: any) => ({
                        fill: true,
                        fillColor: COLORS[p.hazard_level] ?? '#3b82f6',
                        fillOpacity: 0.5,
                        weight: 0,
                    }),
                },
                maxNativeZoom: 18,
            }
        );
        layer.addTo(map);
        return () => { map.removeLayer(layer); };
    }, [api, map]);

    return null;
}