ALTER TABLE scientific_jobs
ADD COLUMN IF NOT EXISTS idempotency_key TEXT UNIQUE;
