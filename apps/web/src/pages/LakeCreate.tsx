import { useState, useEffect } from 'react';
import { useNavigate, Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import apiClient from '../services/apiClient';

// Definimos la estructura para cumplir con las reglas estrictas de TypeScript
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
          if (data.geom) {
            setGeoJsonStr(JSON.stringify(data.geom, null, 2));
          }
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
    return () => { isMounted = false; };
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
      toast.warning('Falta la geometría del lago');
      return;
    }

    let geom;
    try {
      geom = JSON.parse(geoJsonStr);
      if (geom.type !== 'Polygon') {
        setError('El GeoJSON es inválido. El tipo debe ser estrictamente "Polygon".');
        toast.error('GeoJSON inválido');
        return;
      }
      if (!geom.coordinates || !Array.isArray(geom.coordinates)) {
        setError('El GeoJSON carece de un arreglo de coordenadas válido.');
        toast.error('Coordenadas inválidas en GeoJSON');
        return;
      }
    } catch {
      setError('Error de sintaxis: El texto proporcionado no es un JSON válido.');
      toast.error('Error de sintaxis JSON');
      return;
    }

    setIsSubmitting(true);
    try {
      if (isEditMode && initialData) {
        const payload: Record<string, unknown> = {};
        if (name.trim() !== initialData.name) payload.name = name.trim();
        if (region.trim() !== initialData.region) payload.region = region.trim();
        if (description.trim() !== (initialData.description || '')) payload.description = description.trim() || null;
        if (JSON.stringify(geom) !== JSON.stringify(initialData.geom)) payload.geom = geom;

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
          geom 
        });
        toast.success('Lago registrado exitosamente en el catálogo.');
        navigate('/lakes');
      }
    } catch {
      setError('El servidor rechazó la solicitud. Verifica tus permisos o el estado de la API.');
      toast.error('Operación rechazada por el servidor.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center text-gray-500">Cargando datos del lago...</div>;
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">
          {isEditMode ? 'Editar Lago' : 'Registrar Nuevo Lago'}
        </h1>
        <Link to={isEditMode ? `/lakes/${id}` : '/lakes'} className="text-gray-500 hover:text-gray-700 font-medium">
          ← {isEditMode ? 'Volver al detalle' : 'Volver al catálogo'}
        </Link>
      </div>

      <form onSubmit={handleSubmit} className="bg-white p-6 rounded-lg shadow border border-gray-200">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border-l-4 border-red-500 text-red-700 font-medium">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Nombre del Lago *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="Ej. Lago Nahuel Huapi"
              disabled={isSubmitting}
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Región *</label>
            <input
              type="text"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="Ej. Río Negro"
              disabled={isSubmitting}
            />
          </div>
        </div>

        <div className="mb-6">
          <label className="block text-sm font-semibold text-gray-700 mb-2">Descripción (Opcional)</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none h-20"
            placeholder="Añade detalles sobre el cuerpo de agua..."
            disabled={isSubmitting}
          />
        </div>

        <div className="mb-8 p-4 bg-gray-50 border border-gray-200 rounded">
          <div className="flex justify-between items-center mb-2">
            <label className="block text-sm font-semibold text-gray-700">
              Geometría (GeoJSON Polygon) *
            </label>
            <label className="cursor-pointer text-sm font-medium text-blue-600 hover:text-blue-800">
              Cargar Archivo .json
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
            className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none h-40 font-mono text-xs"
            placeholder='{"type": "Polygon", "coordinates": [[[...]]]}'
            disabled={isSubmitting}
          />
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={isSubmitting}
            className={`px-6 py-2 rounded font-semibold text-white ${
              isSubmitting ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
            } transition-colors`}
          >
            {isSubmitting ? 'Guardando...' : (isEditMode ? 'Guardar Cambios' : 'Registrar Lago')}
          </button>
        </div>
      </form>
    </div>
  );
}

