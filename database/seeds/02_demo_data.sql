-- 1. Insertar los 5 lagos requeridos (incluyendo Villarrica) enviando Polígonos
INSERT INTO public.lakes (name, region, status, geom) VALUES 
('Lago Villarrica', 'Araucanía', 'active', ST_GeomFromText('POLYGON((-72.2 -39.2, -72.0 -39.2, -72.0 -39.4, -72.2 -39.4, -72.2 -39.2))', 4326)),
('Lago Llanquihue', 'Los Lagos', 'active', ST_GeomFromText('POLYGON((-73.0 -41.0, -72.8 -41.0, -72.8 -41.2, -73.0 -41.2, -73.0 -41.0))', 4326)),
('Lago Ranco', 'Los Ríos', 'active', ST_GeomFromText('POLYGON((-72.5 -40.1, -72.2 -40.1, -72.2 -40.3, -72.5 -40.3, -72.5 -40.1))', 4326)),
('Lago Todos los Santos', 'Los Lagos', 'active', ST_GeomFromText('POLYGON((-72.3 -41.1, -72.0 -41.1, -72.0 -41.2, -72.3 -41.2, -72.3 -41.1))', 4326)),
('Lago Caburgua', 'Araucanía', 'active', ST_GeomFromText('POLYGON((-71.8 -39.1, -71.7 -39.1, -71.7 -39.2, -71.8 -39.2, -71.8 -39.1))', 4326));

-- 2. Insertar estaciones vinculadas de forma dinámica usando el esquema correcto
DO $$
DECLARE
    v_lake_id UUID;
BEGIN
    -- Buscamos el ID del Lago Villarrica que acabamos de crear en el paso 1
    SELECT id INTO v_lake_id FROM public.lakes WHERE name = 'Lago Villarrica' LIMIT 1;

    -- Insertamos las estaciones usando las columnas obligatorias (code y point)
    INSERT INTO public.stations (lake_id, code, name, point) VALUES 
    (v_lake_id, 'EST-CEN', 'Estación Centro - Villarrica', ST_GeomFromText('POINT(-72.1 -39.2)', 4326)),
    (v_lake_id, 'EST-NOR', 'Estación Norte - Villarrica', ST_GeomFromText('POINT(-72.2 -39.1)', 4326));
END $$;