import { useEffect, useRef, useState } from 'react';
import {
  Map as MapLibreMap,
  NavigationControl,
  type GeoJSONSource,
  type LngLatLike,
} from 'maplibre-gl';
import type { Feature, FeatureCollection, Geometry } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';

export interface BaseMapProps {
  center?: LngLatLike;
  zoom?: number;
  geometries?: FeatureCollection<Geometry> | Feature<Geometry | null>;
}

const initialCenter: LngLatLike = [-72.3316, -39.8142];
const sourceId = 'base-map-geometries';

export default function BaseMap({
  center = initialCenter,
  zoom = 8,
  geometries,
}: BaseMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      center,
      zoom,
      style: {
        version: 8,
        sources: {
          openstreetmap: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '&copy; OpenStreetMap contributors',
          },
        },
        layers: [{
          id: 'openstreetmap',
          type: 'raster',
          source: 'openstreetmap',
        }],
      },
    });

    mapRef.current = map;
    map.addControl(new NavigationControl(), 'top-right');

    const handleLoad = () => setMapLoaded(true);
    map.on('load', handleLoad);

    return () => {
      map.off('load', handleLoad);
      map.remove();
      mapRef.current = null;
      setMapLoaded(false);
    };
  }, [center, zoom]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !geometries) return;

    const mapData = geometries as Parameters<GeoJSONSource['setData']>[0];
    const existingSource = map.getSource(sourceId);
    if (existingSource) {
      (existingSource as GeoJSONSource).setData(mapData);
      return;
    }

    map.addSource(sourceId, { type: 'geojson', data: mapData });
    map.addLayer({
      id: `${sourceId}-fill`,
      type: 'fill',
      source: sourceId,
      paint: {
        'fill-color': '#168a83',
        'fill-opacity': 0.24,
      },
    });
    map.addLayer({
      id: `${sourceId}-line`,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': '#086c67',
        'line-width': 2,
      },
    });
    map.addLayer({
      id: `${sourceId}-point`,
      type: 'circle',
      source: sourceId,
      paint: {
        'circle-radius': 5,
        'circle-color': '#e76f51',
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.5,
      },
    });
  }, [geometries, mapLoaded]);

  return <div ref={containerRef} style={{ width: '100%', height: 400 }} />;
}
