import {
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
  type SyntheticEvent,
} from 'react';
import { apiClient } from '../services/apiClient';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function CsvUploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [isDragging, setIsDragging] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetFileInput = () => {
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const selectValidatedFile = (selectedFile: File | null) => {
    if (!selectedFile) return;

    if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
      setErrorMessage('El archivo seleccionado debe tener extensión .csv');
      setSuccessMessage(null);
      setFile(null);
      setStatus('error');
      resetFileInput();
      return;
    }

    setFile(selectedFile);
    setErrorMessage(null);
    setSuccessMessage(null);
    setStatus('idle');
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0] ?? null;
    selectValidatedFile(selectedFile);
  };

  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (status !== 'uploading') {
      setIsDragging(true);
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (status !== 'uploading' && !isDragging) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
      setIsDragging(false);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (status === 'uploading') return;

    const droppedFile = e.dataTransfer.files?.[0] ?? null;
    selectValidatedFile(droppedFile);
  };

  const handleDropzoneClick = () => {
    if (status !== 'uploading') {
      fileInputRef.current?.click();
    }
  };

  const handleDropzoneKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if ((e.key === 'Enter' || e.key === ' ') && status !== 'uploading') {
      e.preventDefault();
      fileInputRef.current?.click();
    }
  };

  const handleClearFile = () => {
    setFile(null);
    setErrorMessage(null);
    setStatus('idle');
    resetFileInput();
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

      // Usando apiClient apuntando a la ruta exacta sin duplicar /api/v1
      // y sin forzar Content-Type para conservar el boundary multipart.
      await apiClient.post('/imports', formData);

      setStatus('success');
      setSuccessMessage('¡Archivo CSV subido y procesado exitosamente!');

      setFile(null);
      resetFileInput();
    } catch (err: unknown) {
      setStatus('error');
      const message =
        err instanceof Error
          ? err.message
          : 'Ocurrió un error al subir el archivo.';
      setErrorMessage(message);
    }
  };

  const isUploading = status === 'uploading';

  return (
    <section
      className="card"
      style={{ maxWidth: '640px', width: '100%', margin: '0 auto' }}
    >
      <div className="card-head">
        <div>
          <h2>Subir Archivo CSV</h2>
          <p className="card-note">
            Selecciona un archivo con estructura de datos CSV para importar a la plataforma.
          </p>
        </div>
        <span className="badge draft">
          <span aria-hidden="true">📄</span> Formato .CSV
        </span>
      </div>

      <form
        onSubmit={(e) => void handleSubmit(e)}
        className="card-body"
        style={{ display: 'grid', gap: '16px' }}
      >
        <div>
          <label className="label" htmlFor="csv-file-input">
            Archivo CSV
          </label>

          <input
            id="csv-file-input"
            type="file"
            accept=".csv,text/csv"
            ref={fileInputRef}
            onChange={handleFileChange}
            disabled={isUploading}
            style={{
              position: 'absolute',
              width: '1px',
              height: '1px',
              padding: 0,
              margin: '-1px',
              overflow: 'hidden',
              clip: 'rect(0, 0, 0, 0)',
              whiteSpace: 'nowrap',
              border: 0,
            }}
          />

          <div
            role="button"
            tabIndex={isUploading ? -1 : 0}
            aria-label="Zona de arrastre de archivos CSV. Arrastra un archivo aquí o haz clic para seleccionar"
            aria-disabled={isUploading}
            onClick={handleDropzoneClick}
            onKeyDown={handleDropzoneKeyDown}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            style={{
              marginTop: '6px',
              padding: '28px 20px',
              borderRadius: 'var(--radius-sm)',
              border: `2px dashed ${
                isDragging ? 'var(--teal)' : 'var(--line-strong)'
              }`,
              background: isDragging ? 'var(--teal-soft)' : 'var(--ice)',
              textAlign: 'center',
              cursor: isUploading ? 'not-allowed' : 'pointer',
              opacity: isUploading ? 0.65 : 1,
              transition: 'background 0.18s ease, border-color 0.18s ease',
              display: 'grid',
              gap: '8px',
              justifyItems: 'center',
            }}
          >
            <div
              className="kpi-icon"
              aria-hidden="true"
              style={{
                background: isDragging ? 'var(--teal)' : 'var(--teal-soft)',
                color: isDragging ? 'var(--white)' : 'var(--teal)',
                fontSize: '18px',
              }}
            >
              ⬆
            </div>
            <p className="cell-title" style={{ fontSize: '13.5px' }}>
              {isDragging
                ? 'Suelta el archivo CSV aquí para cargarlo'
                : 'Arrastra y suelta tu archivo CSV aquí'}
            </p>
            <p className="subtitle" style={{ fontSize: '12px' }}>
              o haz clic en esta área para explorar desde tu equipo
            </p>
            <span className="btn btn-secondary btn-sm" aria-hidden="true">
              Seleccionar archivo .csv
            </span>
          </div>
        </div>

        {file && (
          <div
            className="queue-card"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              flexWrap: 'wrap',
              padding: '12px 14px',
            }}
          >
            <div style={{ display: 'grid', gap: '4px' }}>
              <span className="cell-title">{file.name}</span>
              <span className="card-note">
                Tamaño: <span className="code-pill">{formatFileSize(file.size)}</span>
              </span>
            </div>
            <div className="head-actions">
              <span className="badge validated">
                <span aria-hidden="true">✓</span> Listo para subir
              </span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleClearFile}
                disabled={isUploading}
              >
                Quitar
              </button>
            </div>
          </div>
        )}

        {errorMessage && (
          <div className="status-banner danger" role="alert">
            <span>
              <span aria-hidden="true">⚠️</span> {errorMessage}
            </span>
          </div>
        )}

        {successMessage && (
          <div className="status-banner success" role="status">
            <span>
              <span aria-hidden="true">✓</span> {successMessage}
            </span>
          </div>
        )}

        <button
          type="submit"
          disabled={!file || isUploading}
          className="btn btn-primary"
          style={{ width: '100%' }}
        >
          {isUploading ? 'Subiendo archivo...' : 'Enviar CSV'}
        </button>
      </form>
    </section>
  );
}



