import { useState, useEffect } from 'react';
import { useNavigate, Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import apiClient from '../services/apiClient';

interface LakeFormData {
  name?: string;
  region?: string;
  description?: string | null;
  geom?: unknown;
}

export default function LakeCreate() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEditMode = Boolean(id);

  const [name, setName] = useState('');
  const [region, setRegion] = useState('');
  const [description, setDescription] = useState('');
  const [geoJsonStr, setGeoJsonStr] = useState('');
  const [initialData, setInitialData] = useState<LakeFormData | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(isEditMode);

  useEffect(() => {
    if (!isEditMode) return;
    let isMounted = true;
    const fetchLake = async () => {
      try {
        const data = await apiClient.get<LakeFormData>(`lakes/${id}`);
        if (isMounted) {
          setName(data.name || '');
          setRegion(data.region || '');
          setDescription(data.description || '');
          if (data.geom) setGeoJsonStr(JSON.stringify(data.geom, null, 2));
          setInitialData(data);
        }
      } catch {
        if (isMounted) {
          setError('No se pudo cargar la información del lago.');
          toast.error('Error de red al cargar el lago.');
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    void fetchLake();
    return () => {
      isMounted = false;
    };
  }, [id, isEditMode]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result;
      if (typeof content === 'string') {
        setGeoJsonStr(content);
        toast.success('Archivo cargado correctamente.');
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim() || !region.trim()) {
      setError('El nombre y la región son campos obligatorios.');
      toast.warning('Datos incompletos');
      return;
    }

    if (!geoJsonStr.trim()) {
      setError('Debes proporcionar la geometría del lago (GeoJSON).');
      toast.warning('Falta la geometría');
      return;
    }

    let geom;
    try {
      geom = JSON.parse(geoJsonStr);
      if (geom.type !== 'Polygon') throw new Error('Tipo debe ser Polygon');
      if (!geom.coordinates || !Array.isArray(geom.coordinates))
        throw new Error('Coordenadas inválidas');
    } catch {
      setError(
        'Error de sintaxis: GeoJSON inválido. Asegura que el tipo sea "Polygon".'
      );
      toast.error('GeoJSON inválido');
      return;
    }

    setIsSubmitting(true);
    try {
      if (isEditMode && initialData) {
        const payload: Record<string, unknown> = {};
        if (name.trim() !== initialData.name) payload.name = name.trim();
        if (region.trim() !== initialData.region)
          payload.region = region.trim();
        if (description.trim() !== (initialData.description || ''))
          payload.description = description.trim() || null;
        if (JSON.stringify(geom) !== JSON.stringify(initialData.geom))
          payload.geom = geom;

        if (Object.keys(payload).length === 0) {
          toast.warning('No hay cambios para guardar.');
          setIsSubmitting(false);
          return;
        }

        await apiClient.patch(`lakes/${id}`, payload);
        toast.success('Lago actualizado correctamente.');
        navigate(`/lakes/${id}`);
      } else {
        await apiClient.post('lakes', {
          name: name.trim(),
          region: region.trim(),
          description: description.trim() || null,
          geom,
        });
        toast.success('Lago registrado exitosamente.');
        navigate('/lakes');
      }
    } catch {
      setError('El servidor rechazó la solicitud.');
      toast.error('Operación rechazada.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center text-gray-500">
        Cargando datos del formulario...
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto w-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
        <h1 className="text-2xl md:text-3xl font-bold text-gray-800">
          {isEditMode ? 'Editar Lago' : 'Registrar Nuevo Lago'}
        </h1>
        <Link
          to={isEditMode ? `/lakes/${id}` : '/lakes'}
          className="text-blue-600 hover:text-blue-800 font-medium whitespace-nowrap text-sm md:text-base"
        >
          ← {isEditMode ? 'Volver al detalle' : 'Volver al catálogo'}
        </Link>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-white p-4 md:p-8 rounded-xl shadow-sm border border-gray-200"
      >
        {error && (
          <div className="mb-6 p-4 bg-red-50 border-l-4 border-red-500 text-red-700 font-medium text-sm rounded-r-lg">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 mb-6">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Nombre del Lago *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="Ej. Lago Llanquihue"
              disabled={isSubmitting}
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Región *
            </label>
            <input
              type="text"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="Ej. Los Lagos"
              disabled={isSubmitting}
            />
          </div>
        </div>

        <div className="mb-6">
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Descripción (Opcional)
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none h-24 resize-y"
            placeholder="Añade detalles sobre el cuerpo de agua..."
            disabled={isSubmitting}
          />
        </div>

        <div className="mb-8 bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center p-4 border-b border-gray-200 gap-3">
            <label className="block text-sm font-semibold text-gray-700">
              Geometría (GeoJSON Polygon) *
            </label>
            <label className="cursor-pointer text-sm font-semibold text-blue-600 hover:text-blue-800 bg-blue-50 px-3 py-1.5 rounded border border-blue-100 transition-colors">
              Subir Archivo .json
              <input
                type="file"
                accept=".json,application/json"
                className="hidden"
                onChange={handleFileUpload}
                disabled={isSubmitting}
              />
            </label>
          </div>
          <textarea
            value={geoJsonStr}
            onChange={(e) => setGeoJsonStr(e.target.value)}
            className="w-full p-4 focus:ring-0 outline-none h-48 md:h-64 font-mono text-xs md:text-sm bg-gray-50 text-gray-800 resize-y"
            placeholder='{"type": "Polygon", "coordinates": [[[...]]]}'
            disabled={isSubmitting}
          />
        </div>

        <div className="flex justify-end border-t border-gray-100 pt-6">
          <button
            type="submit"
            disabled={isSubmitting}
            className={`w-full sm:w-auto px-8 py-3 rounded-lg font-bold text-white shadow-sm transition-all ${
              isSubmitting
                ? 'bg-blue-400 cursor-wait'
                : 'bg-blue-600 hover:bg-blue-700 hover:shadow'
            }`}
          >
            {isSubmitting
              ? 'Procesando...'
              : isEditMode
                ? 'Guardar Cambios'
                : 'Registrar Lago'}
          </button>
        </div>
      </form>
    </div>
  );
}
