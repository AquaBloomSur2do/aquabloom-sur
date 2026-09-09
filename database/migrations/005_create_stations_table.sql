CREATE TABLE public.stations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lake_id UUID NOT NULL REFERENCES public.lakes(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    point GEOMETRY(Point, 4326) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    
    UNIQUE(lake_id, code)
);

CREATE TRIGGER set_stations_updated_at
BEFORE UPDATE ON public.stations
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();
