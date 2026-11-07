-- Tarea: S2-142
ALTER TABLE dataset.versions
ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
