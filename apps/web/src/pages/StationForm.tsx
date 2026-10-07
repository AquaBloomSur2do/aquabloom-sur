import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import apiClient from '../services/apiClient';

interface StationRecord {
  id: string;
  code: string;
  name: string;
  description: string | null;
  status: string;
  point: { coordinates: [number, number] };
}

export function StationForm() {
  const { lakeId, stationId } = useParams<{
    lakeId: string;
    stationId?: string;
  }>();
  const navigate = useNavigate();
  const isEditMode = Boolean(stationId);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [status, setStatus] = useState('active');
  const [isLoading, setIsLoading] = useState(isEditMode);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!lakeId || !stationId) return;
    let isMounted = true;

    const loadStation = async () => {
      try {
        const stations = await apiClient.get<StationRecord[]>(
          `lakes/${lakeId}/stations`,
        );
        const station = stations.find((candidate) => candidate.id === stationId);
        if (!station) throw new Error('No se encontró la estación.');

        if (isMounted) {
          setCode(station.code);
          setName(station.name);
          setDescription(station.description ?? '');
          setLongitude(String(station.point.coordinates[0]));
          setLatitude(String(station.point.coordinates[1]));
          setStatus(station.status.toLowerCase());
        }
      } catch {
        if (isMounted) setError('No se pudo cargar la estación.');
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    void loadStation();
    return () => {
      isMounted = false;
    };
  }, [lakeId, stationId]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!lakeId) return;

    setError(null);
    setIsSubmitting(true);
    const coordinates = {
      latitude: Number(String(latitude).replace(',', '.')),
      longitude: Number(String(longitude).replace(',', '.')),
    };

    try {
      if (isEditMode && stationId) {
        // Enviar solo los campos definidos para PATCH en StationUpdate
        await apiClient.patch(`stations/${stationId}`, {
          name: name.trim() || null,
          description: description.trim() || null,
          coordinates,
          status,
        });
        toast.success('Estación actualizada.');
      } else {
        // Enviar payload plano para POST (ajustado a las expectativas típicas)
        await apiClient.post(`lakes/${lakeId}/stations`, {
          code: code.trim(),
          name: name.trim(),
          description: description.trim() || null,
          latitude: coordinates.latitude,
          longitude: coordinates.longitude,
        });
        toast.success('Estación creada.');
      }
      navigate(`/lakes/${lakeId}`);
    } catch (submitError) {
      const message =
        submitError instanceof Error
          ? submitError.message
          : 'No se pudo guardar la estación.';
      setError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center">Cargando estación...</div>;
  }

  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto w-full">
      <header className="lakes-header">
        <div>
          <p className="eyebrow">Estaciones</p>
          <h1>{isEditMode ? 'Editar estación' : 'Registrar estación'}</h1>
        </div>
        <Link className="btn btn-secondary" to={`/lakes/${lakeId}`}>
          Volver al lago
        </Link>
      </header>

      <form className="mt-6 bg-white p-6 rounded-lg border border-gray-200 space-y-5" onSubmit={handleSubmit}>
        {error && <p className="state-panel state-panel--error" role="alert">{error}</p>}

        {!isEditMode && (
          <label className="block text-sm font-semibold text-gray-700">
            Código
            <input className="mt-1 w-full p-2 border rounded" value={code} onChange={(event) => setCode(event.target.value)} required />
          </label>
        )}

        <label className="block text-sm font-semibold text-gray-700">
          Nombre
          <input className="mt-1 w-full p-2 border rounded" value={name} onChange={(event) => setName(event.target.value)} required />
        </label>

        <label className="block text-sm font-semibold text-gray-700">
          Descripción
          <textarea className="mt-1 w-full p-2 border rounded" value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block text-sm font-semibold text-gray-700">
            Latitud
            <input className="mt-1 w-full p-2 border rounded" type="text" value={latitude} onChange={(event) => setLatitude(event.target.value)} required />
          </label>
          <label className="block text-sm font-semibold text-gray-700">
            Longitud
            <input className="mt-1 w-full p-2 border rounded" type="text" value={longitude} onChange={(event) => setLongitude(event.target.value)} required />
          </label>
        </div>

        {isEditMode && (
          <label className="block text-sm font-semibold text-gray-700">
            Estado
            <select className="mt-1 w-full p-2 border rounded" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="active">Activa</option>
              <option value="inactive">Inactiva</option>
            </select>
          </label>
        )}

        <button className="btn btn-primary" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Guardando...' : isEditMode ? 'Guardar cambios' : 'Registrar estación'}
        </button>
      </form>
    </div>
  );
}