-- Datos semilla mínimos para los cinco lagos principales
INSERT INTO public.lakes (name, region, description, geom, status) 
VALUES
  ('Lago Panguipulli', 'Los Ríos', 'Geometría preliminar no oficial, pendiente de reemplazo.', ST_GeomFromText('POLYGON((-72.15 -39.68, -72.08 -39.68, -72.08 -39.75, -72.15 -39.75, -72.15 -39.68))', 4326), 'active'),
  ('Lago Villarrica', 'La Araucanía', 'Geometría preliminar no oficial, pendiente de reemplazo.', ST_GeomFromText('POLYGON((-72.15 -39.22, -72.05 -39.22, -72.05 -39.30, -72.15 -39.30, -72.15 -39.22))', 4326), 'active'),
  ('Lago Calafquén', 'Los Ríos/La Araucanía', 'Geometría preliminar no oficial, pendiente de reemplazo.', ST_GeomFromText('POLYGON((-72.18 -39.50, -72.08 -39.50, -72.08 -39.58, -72.18 -39.58, -72.18 -39.50))', 4326), 'active'),
  ('Lago Riñihue', 'Los Ríos', 'Geometría preliminar no oficial, pendiente de reemplazo.', ST_GeomFromText('POLYGON((-72.35 -39.78, -72.25 -39.78, -72.25 -39.85, -72.35 -39.85, -72.35 -39.78))', 4326), 'active'),
  ('Lago Ranco', 'Los Ríos', 'Geometría preliminar no oficial, pendiente de reemplazo.', ST_GeomFromText('POLYGON((-72.43 -40.15, -72.33 -40.15, -72.33 -40.25, -72.43 -40.25, -72.43 -40.15))', 4326), 'active');
