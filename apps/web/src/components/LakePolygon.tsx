import React, { useEffect, useRef } from 'react';
import { GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { FeatureCollection, Geometry, Feature } from 'geojson';

import 'leaflet/dist/leaflet.css';

interface LakePolygonProps {
    geojsonData: FeatureCollection<Geometry> | Feature<Geometry> | null;
}

export const LakePolygon: React.FC<LakePolygonProps> = ({ geojsonData }) => {
    const map = useMap(); 
    const geoJsonRef = useRef<L.GeoJSON>(null);

    useEffect(() => {
        if (geojsonData && geoJsonRef.current) {
            const bounds = geoJsonRef.current.getBounds();
            
            if (bounds.isValid()) {
                map.fitBounds(bounds, { 
                    padding: [40, 40], 
                    animate: true 
                });
            }
        }
    }, [geojsonData, map]); 

    if (!geojsonData) return null;

    const getStableKey = () => {
        if (geojsonData.bbox) return JSON.stringify(geojsonData.bbox);
        
        if ('features' in geojsonData && geojsonData.features[0]?.id) {
             return String(geojsonData.features[0].id);
        }
        
        if ('properties' in geojsonData && geojsonData.properties?.name) {
             return String(geojsonData.properties.name);
        }
        
        return JSON.stringify(geojsonData.type) + JSON.stringify(geojsonData);
    };

    const dynamicKey = getStableKey();

    return (
        <GeoJSON 
            key={dynamicKey}
            data={geojsonData} 
            ref={geoJsonRef}
            style={{ color: '#2563eb', weight: 2, fillOpacity: 0.3 }}
        />
    );
};
