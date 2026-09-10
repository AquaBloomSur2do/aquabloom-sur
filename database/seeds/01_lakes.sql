-- Datos semilla mínimos para los cinco lagos principales
INSERT INTO catalog.lake (lake_id, name, region, geometry, crs, status, metadata) 
VALUES
  (gen_random_uuid(), 'Lago Panguipulli', 'Los Ríos', 'POINT(-72.1167 -39.7167)', 'EPSG:4326', 'active', '{"test_geometry": true, "unofficial": true, "action": "reemplazar_posteriormente"}'),
  (gen_random_uuid(), 'Lago Villarrica', 'La Araucanía', 'POINT(-72.1000 -39.2667)', 'EPSG:4326', 'active', '{"test_geometry": true, "unofficial": true, "action": "reemplazar_posteriormente"}'),
  (gen_random_uuid(), 'Lago Calafquén', 'Los Ríos/La Araucanía', 'POINT(-72.1333 -39.5333)', 'EPSG:4326', 'active', '{"test_geometry": true, "unofficial": true, "action": "reemplazar_posteriormente"}'),
  (gen_random_uuid(), 'Lago Riñihue', 'Los Ríos', 'POINT(-72.3000 -39.8167)', 'EPSG:4326', 'active', '{"test_geometry": true, "unofficial": true, "action": "reemplazar_posteriormente"}'),
  (gen_random_uuid(), 'Lago Ranco', 'Los Ríos', 'POINT(-72.3833 -40.2000)', 'EPSG:4326', 'active', '{"test_geometry": true, "unofficial": true, "action": "reemplazar_posteriormente"}');
  