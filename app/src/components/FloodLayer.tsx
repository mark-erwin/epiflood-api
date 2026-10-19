import { useEffect } from 'react';
import type OLMap from 'ol/Map';
import VectorTileLayer from 'ol/layer/VectorTile';
import VectorTileSource from 'ol/source/VectorTile';
import MVT from 'ol/format/MVT';
import { Fill, Style } from 'ol/style';
import type { FeatureLike } from 'ol/Feature';

// Same colors as before, with the 0.5 fill opacity baked into the alpha channel
const COLORS: Record<number, string> = {
    1: 'rgba(180, 209, 226, 0.5)', // #b4d1e2
    2: 'rgba(95, 163, 206, 0.5)',  // #5fa3ce
    3: 'rgba(43, 117, 178, 0.5)',  // #2b75b2
};
const FALLBACK = 'rgba(59, 130, 246, 0.5)'; // #3b82f6

// One shared Style per hazard level instead of a new object per feature
const styleCache: Record<string, Style> = {};
function styleFor(level: number): Style {
    const color = COLORS[level] ?? FALLBACK;
    return (styleCache[color] ??= new Style({ fill: new Fill({ color }) }));
}

interface Props {
    map: OLMap;
    api: string;
}

export default function FloodLayer({ map, api }: Props) {
    useEffect(() => {
        const layer = new VectorTileLayer({
            zIndex: 5, // below the health-unit markers (zIndex 10)
            source: new VectorTileSource({
                format: new MVT({ layers: ['flood'] }), // only read the "flood" tile layer
                url: `${api}/flood-tiles/{z}/{x}/{y}.pbf`,
                maxZoom: 18, // equivalent of maxNativeZoom: tiles are overzoomed beyond this
            }),
            style: (feature: FeatureLike) => styleFor(feature.get('hazard_level')),
        });

        map.addLayer(layer);
        return () => {
            map.removeLayer(layer);
            layer.dispose();
        };
    }, [map, api]);

    return null;
}
