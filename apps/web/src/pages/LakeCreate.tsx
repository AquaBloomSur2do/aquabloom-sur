import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import apiClient from '../services/apiClient';

export default function LakeCreate() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [region, setRegion] = useState('');
  const [description, setDescription] = useState('');
  const [geoJsonStr, setGeoJsonStr] = useState('');
  
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Procesador del archivo GeoJSON cargado localmente
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result;
      if (typeof content === 'string') {
        setGeoJsonStr(content);
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // 1. Barrera de validación estructural
    if (!name.trim() || !region.trim()) {
      setError('El nombre y la región son campos obligatorios.');
      return;
    }

    if (!geoJsonStr.trim()) {
      setError('Debes proporcionar la geometría del lago (GeoJSON).');
      return;
    }

    // 2. Barrera de validación espacial (Client-side)
    let geom;
    try {
      geom = JSON.parse(geoJsonStr);
      if (geom.type !== 'Polygon') {
        setError('El GeoJSON es inválido. El tipo debe ser estrictamente "Polygon".');
        return;
      }
      if (!geom.coordinates || !Array.isArray(geom.coordinates)) {
        setError('El GeoJSON carece de un arreglo de coordenadas válido.');
        return;
      }
    } catch {
      setError('Error de sintaxis: El texto proporcionado no es un JSON válido.');
      return;
    }

    // 3. Transacción de red
    setIsSubmitting(true);
    try {
      await apiClient.post('/lakes', { 
        name: name.trim(), 
        region: region.trim(), 
        description: description.trim() || null, 
        geom 
      });
      // Criterio de aceptación: Redirección al catálogo tras la creación
      navigate('/lakes');
    } catch {
      setError('El servidor rechazó la solicitud. Verifica tus permisos de curador o el estado de la API.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Registrar Nuevo Lago</h1>
        <Link to="/lakes" className="text-gray-500 hover:text-gray-700 font-medium">
          ← Volver al catálogo
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
            {isSubmitting ? 'Registrando...' : 'Registrar Lago'}
          </button>
        </div>
      </form>
    </div>
  );
}

