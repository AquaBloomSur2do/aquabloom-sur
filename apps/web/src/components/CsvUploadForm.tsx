import { useState, type ChangeEvent, type SyntheticEvent } from 'react';
import { apiClient } from '../services/apiClient';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

export function CsvUploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      
      // Validación estricta de formato .csv
      if (!selectedFile.name.endsWith('.csv')) {
        setErrorMessage('El archivo seleccionado debe tener extensión .csv');
        setFile(null);
        return;
      }

      setFile(selectedFile);
      setErrorMessage(null);
      setStatus('idle');
    }
  };

  const handleSubmit = async (e: SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!file) {
      setErrorMessage('Por favor selecciona un archivo CSV válido.');
      return;
    }

    setStatus('uploading');
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      // Usando apiClient correctamente para respetar la autenticación JWT y rutas relativas
      await apiClient.post('/api/v1/imports/csv', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setStatus('success');
      setSuccessMessage('¡Archivo CSV subido y procesado exitosamente!');
      setFile(null);
    } catch (err: unknown) {
      setStatus('error');
      const message = err instanceof Error ? err.message : 'Ocurrió un error al subir el archivo.';
      setErrorMessage(message);
    }
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 max-w-md mx-auto mt-6">
      <h2 className="text-lg font-bold text-gray-800 mb-2">Subir Archivo CSV</h2>
      <p className="text-sm text-gray-600 mb-4">
        Selecciona un archivo con estructura de datos CSV para importar a la plataforma.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="csv-file-input">
            Archivo CSV
          </label>
          <input
            id="csv-file-input"
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            disabled={status === 'uploading'}
            className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
        </div>

        {errorMessage && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg" role="alert">
            {errorMessage}
          </div>
        )}

        {successMessage && (
          <div className="p-3 bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg" role="status">
            {successMessage}
          </div>
        )}

        <button
          type="submit"
          disabled={!file || status === 'uploading'}
          className={`w-full py-2 px-4 rounded-lg text-white font-medium transition-colors ${
            !file || status === 'uploading'
              ? 'bg-gray-300 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          {status === 'uploading' ? 'Subiendo archivo...' : 'Enviar CSV'}
        </button>
      </form>
    </div>
  );
}