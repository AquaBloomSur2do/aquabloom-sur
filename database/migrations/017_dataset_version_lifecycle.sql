-- Migration 017: Alinear estados del ciclo de vida en dataset.versions

-- 1. Eliminar restricciones antiguas antes de modificar datos para evitar fallos de CHECK
ALTER TABLE dataset.versions
  DROP CONSTRAINT IF EXISTS versions_status_check,
  DROP CONSTRAINT IF EXISTS dataset_versions_status_check,
  DROP CONSTRAINT IF EXISTS versions_state_check,
  DROP CONSTRAINT IF EXISTS dataset_versions_state_check;

-- 2. Asegurar existencia de la columna state
ALTER TABLE dataset.versions
  ADD COLUMN IF NOT EXISTS state VARCHAR(50) DEFAULT 'DRAFT';

-- 3. Actualizar los valores existentes a mayúsculas en ambas columnas
UPDATE dataset.versions
SET state = UPPER(COALESCE(state, status, 'DRAFT')),
    status = UPPER(COALESCE(status, state, 'DRAFT'));

-- 4. Aplicar restricciones CHECK actualizadas para admitir los 5 estados del ciclo de vida
ALTER TABLE dataset.versions
  ADD CONSTRAINT dataset_versions_state_check
  CHECK (state IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED')),
  ADD CONSTRAINT dataset_versions_status_check
  CHECK (status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED'));
  