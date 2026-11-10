import { useEffect, useRef, useState } from 'react';
import {
  Map as MapLibreMap,
  NavigationControl,
  Popup,
  type GeoJSONSource,
  type LngLatLike,
  type MapLayerMouseEvent,
} from 'maplibre-gl';
import { useNavigate } from 'react-router-dom';
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
  const navigate = useNavigate();

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
        layers: [
          {
            id: 'openstreetmap',
            type: 'raster',
            source: 'openstreetmap',
          },
        ],
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

    const handleFeatureClick = (e: MapLayerMouseEvent) => {
      if (!e.features || e.features.length === 0) return;

      const properties = e.features[0].properties;
      const name = properties.nombre || 'Sin nombre';
      const id = properties.id;

      const htmlContent = `
        <div style="display: flex; flex-direction: column; gap: 8px; font-family: sans-serif;">
          <h3 style="margin: 0; font-size: 16px; font-weight: bold; color: #111827;">${name}</h3>
          <button id="btn-detail-${id}" style="color: #2563eb; text-decoration: underline; background: none; border: none; padding: 0; text-align: left; cursor: pointer; font-size: 14px;">
            Ver detalle completo
          </button>
        </div>
      `;

      const popup = new Popup({ closeButton: true, closeOnClick: true })
        .setLngLat(e.lngLat)
        .setHTML(htmlContent)
        .addTo(map);

      document
        .getElementById(`btn-detail-${id}`)
        ?.addEventListener('click', () => {
          navigate(`/lakes/${id}`);
          popup.remove();
        });
    };

    const setCursorPointer = () => {
      map.getCanvas().style.cursor = 'pointer';
    };
    const resetCursor = () => {
      map.getCanvas().style.cursor = '';
    };

    const interactiveLayers = [`${sourceId}-fill`, `${sourceId}-point`];
    interactiveLayers.forEach((layerId) => {
      map.on('click', layerId, handleFeatureClick);
      map.on('mouseenter', layerId, setCursorPointer);
      map.on('mouseleave', layerId, resetCursor);
    });
  }, [geometries, mapLoaded, navigate]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full min-h-[300px] md:min-h-[400px] z-0"
    />
  );
}
