CREATE TABLE IF NOT EXISTS public.imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    content_type TEXT,
    checksum CHAR(64) NOT NULL UNIQUE,
    file_size BIGINT NOT NULL CHECK (file_size > 0),
    idempotency_key VARCHAR(255) UNIQUE,
    storage_path TEXT NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO storage.buckets (id, name, public)
VALUES ('imports', 'imports', FALSE)
ON CONFLICT (id) DO NOTHING;