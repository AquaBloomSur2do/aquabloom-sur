import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { ListPageState } from '../components/ListPageState';
import { apiClient } from '../services/apiClient';

interface OrganizationSummary {
  id: string;
  name: string;
  role: string;
}

export function OrganizationsList() {
  const [organizations, setOrganizations] = useState<OrganizationSummary[]>([]);
  const [name, setName] = useState('');
  const [identifier, setIdentifier] = useState('');
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOrganizations = useCallback(async () => {
    try {
      const result = await apiClient.get<OrganizationSummary[]>('organizations/');
      setOrganizations(result);
      setError(null);
    } catch (fetchError) {
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

  const createOrganization = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsCreating(true);
    setError(null);

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
    } catch (createError) {
      const message = createError instanceof Error ? createError.message : 'No se pudo crear la organización.';
      setError(message);
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
    >
      <div className="space-y-8">
        <form onSubmit={createOrganization} className="bg-white p-5 rounded-lg border border-gray-200 space-y-4">
          <h2 className="text-lg font-semibold">Crear organización</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="text-sm font-medium">
              Nombre
              <input className="mt-1 w-full p-2 border rounded" value={name} onChange={(event) => setName(event.target.value)} required />
            </label>
            <label className="text-sm font-medium">
              Identificador
              <input className="mt-1 w-full p-2 border rounded" value={identifier} onChange={(event) => setIdentifier(event.target.value)} pattern="[a-z0-9-]+" title="Usa minúsculas, números y guiones." required />
            </label>
          </div>
          <label className="block text-sm font-medium">
            Descripción
            <textarea className="mt-1 w-full p-2 border rounded" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <button className="btn btn-primary" type="submit" disabled={isCreating}>
            {isCreating ? 'Creando...' : 'Crear organización'}
          </button>
        </form>

        {organizations.length === 0 ? (
          <div className="state-panel state-panel--empty">No tienes organizaciones visibles.</div>
        ) : (
          <div className="lakes-table-wrapper">
            <table className="lakes-table">
              <thead>
                <tr><th>Organización</th><th>Tu rol</th><th>Acción</th></tr>
              </thead>
              <tbody>
                {organizations.map((organization) => (
                  <tr key={organization.id}>
                    <td>{organization.name}</td>
                    <td>{organization.role}</td>
                    <td><Link className="btn btn-secondary" to="/members">Administrar miembros</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </ListPageState>
  );
}