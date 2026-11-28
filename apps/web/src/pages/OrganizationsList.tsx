import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { ListPageState } from '../components/ListPageState';
import { apiClient } from '../services/apiClient';

interface OrganizationSummary {
  id: string;
  name: string;
  role: string;
}

const isForbiddenError = (error: unknown): boolean =>
  Boolean(error && typeof error === 'object' && 'status' in error && error.status === 403);

function renderRoleBadge(role: string) {
  const normalized = role.trim().toLowerCase();
  if (normalized.includes('admin')) {
    return (
      <span className="badge restricted">
        <span aria-hidden="true">🛡️</span> {role}
      </span>
    );
  }
  if (normalized.includes('cient') || normalized.includes('invest')) {
    return (
      <span className="badge validated">
        <span aria-hidden="true">🔬</span> {role}
      </span>
    );
  }
  return (
    <span className="badge draft">
      <span aria-hidden="true">👤</span> {role}
    </span>
  );
}

export function OrganizationsList() {
  const [organizations, setOrganizations] = useState<OrganizationSummary[]>([]);
  const [name, setName] = useState('');
  const [identifier, setIdentifier] = useState('');
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);

  const fetchOrganizations = useCallback(async () => {
    try {
      const result = await apiClient.get<OrganizationSummary[]>('organizations/');
      setOrganizations(result);
      setError(null);
      setIsForbidden(false);
    } catch (fetchError) {
      setIsForbidden(isForbiddenError(fetchError));
      setError(
        fetchError instanceof Error
          ? fetchError.message
          : 'No se pudieron cargar las organizaciones.',
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchOrganizations();
  }, [fetchOrganizations]);

  const createOrganization = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsCreating(true);
    setCreateError(null);

    try {
      await apiClient.post('organizations', {
        name: name.trim(),
        identifier: identifier.trim(),
        description: description.trim() || null,
      });
      setName('');
      setIdentifier('');
      setDescription('');
      toast.success('Organización creada.');
      await fetchOrganizations();
    } catch (submitError) {
      const message =
        submitError instanceof Error
          ? submitError.message
          : 'No se pudo crear la organización.';
      setCreateError(message);
      toast.error(message);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <ListPageState
      eyebrow="Administración"
      title="Organizaciones"
      isLoading={isLoading}
      loadingMessage="Cargando organizaciones..."
      error={error}
      isEmpty={false}
      emptyMessage="No tienes organizaciones visibles."
      onRetry={() => void fetchOrganizations()}
      isForbidden={isForbidden}
      forbiddenMessage="No tienes permisos para consultar las organizaciones."
    >
      <div style={{ display: 'grid', gap: '20px' }}>
        <form
          onSubmit={(event) => void createOrganization(event)}
          className="card"
        >
          <div className="card-head">
            <div>
              <h2>Crear organización</h2>
              <p className="card-note">
                Define un espacio aislado multitenant para gestionar lagos, estaciones y datasets.
              </p>
            </div>
          </div>

          <div
            className="card-body"
            style={{ display: 'grid', gap: '16px' }}
          >
            {createError && (
              <div className="status-banner danger" role="alert">
                <span>
                  <span aria-hidden="true">⚠️</span> {createError}
                </span>
              </div>
            )}

            <div className="grid grid-2">
              <label className="label" htmlFor="org-name">
                Nombre
                <input
                  id="org-name"
                  className="control"
                  placeholder="Ej: Centro Limnológico Araucanía"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                />
              </label>

              <label className="label" htmlFor="org-identifier">
                Identificador
                <input
                  id="org-identifier"
                  className="control"
                  style={{ fontFamily: 'var(--mono)' }}
                  placeholder="Ej: centro-araucania"
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  pattern="[a-z0-9-]+"
                  title="Usa minúsculas, números y guiones."
                  required
                />
                <span className="card-note">
                  Solo minúsculas, números y guiones.
                </span>
              </label>
            </div>

            <label className="label" htmlFor="org-description">
              Descripción
              <textarea
                id="org-description"
                className="control"
                placeholder="Alcance institucional o área geográfica monitoreada..."
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={2}
              />
            </label>

            <div
              className="head-actions"
              style={{ justifyContent: 'flex-end' }}
            >
              <button
                className="btn btn-primary"
                type="submit"
                disabled={isCreating}
              >
                {isCreating ? 'Creando...' : 'Crear organización'}
              </button>
            </div>
          </div>
        </form>

        <section className="card" aria-label="Listado de organizaciones">
          <div className="card-head">
            <div>
              <h2>Organizaciones registradas</h2>
              <p className="card-note">
                Organizaciones en las que posees membresía activa.
              </p>
            </div>
            <span className="badge restricted">
              <span aria-hidden="true">🏢</span> {organizations.length}{' '}
              {organizations.length === 1 ? 'organización' : 'organizaciones'}
            </span>
          </div>

          {organizations.length === 0 ? (
            <div className="card-body">
              <p className="subtitle">No tienes organizaciones visibles.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Organización</th>
                    <th>Tu rol</th>
                    <th>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {organizations.map((organization) => (
                    <tr key={organization.id}>
                      <td className="cell-title">{organization.name}</td>
                      <td>{renderRoleBadge(organization.role)}</td>
                      <td>
                        <Link
                          className="btn btn-secondary btn-sm"
                          to="/members"
                        >
                          Administrar miembros
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </ListPageState>
  );
}


