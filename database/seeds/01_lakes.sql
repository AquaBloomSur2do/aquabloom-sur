-- Datos semilla mínimos para los cinco lagos principales
INSERT INTO public.lakes (lake_id, name, region, geom, crs, status, metadata) 
VALUES
  (gen_random_uuid(), 'Lago Panguipulli', 'Los Ríos', ST_GeomFromText('POINT(-72.1167 -39.7167)', 4326), 'EPSG:4326', 'active', '{"test_geometry": true, "unofficial": true, "action": "reemplazar_posteriormente"}'),
  (gen_random_uuid(), 'Lago Villarrica', 'La Araucanía', ST_GeomFromText('POINT(-72.1000 -39.2667)', 4326), 'EPSG:4326', 'active', '{"test_geometry": true, "unofficial": true, "action": "reemplazar_posteriormente"}'),
  (gen_random_uuid(), 'Lago Calafquén', 'Los Ríos/La Araucanía', ST_GeomFromText('POINT(-72.1333 -39.5333)', 4326), 'EPSG:4326', 'active', '{"test_geometry": true, "unofficial": true, "action": "reemplazar_posteriormente"}'),
  (gen_random_uuid(), 'Lago Riñihue', 'Los Ríos', ST_GeomFromText('POINT(-72.3000 -39.8167)', 4326), 'EPSG:4326', 'active', '{"test_geometry": true, "unofficial": true, "action": "reemplazar_posteriormente"}'),
  (gen_random_uuid(), 'Lago Ranco', 'Los Ríos', ST_GeomFromText('POINT(-72.3833 -40.2000)', 4326), 'EPSG:4326', 'active', '{"test_geometry": true, "unofficial": true, "action": "reemplazar_posteriormente"}');
  