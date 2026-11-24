import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { NumericFormat } from 'react-number-format';
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

function getPreferredDecimalSeparator(): ',' | '.' {
  if (typeof navigator !== 'undefined' && navigator.language.startsWith('es')) {
    return ',';
  }
  return '.';
}

export function StationForm() {
  const { lakeId, stationId } = useParams<{
    lakeId: string;
    stationId?: string;
  }>();
  const navigate = useNavigate();
  const isEditMode = Boolean(stationId);
  const decimalSeparator = getPreferredDecimalSeparator();

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
        const station = stations.find(
          (candidate) => candidate.id === stationId,
        );
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

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!lakeId) return;

    setError(null);

    const parsedLat = Number(latitude);
    const parsedLng = Number(longitude);

    if (
      !Number.isFinite(parsedLat) ||
      parsedLat < -90 ||
      parsedLat > 90
    ) {
      const message = 'La latitud debe ser un valor numérico entre -90 y 90.';
      setError(message);
      toast.error(message);
      return;
    }

    if (
      !Number.isFinite(parsedLng) ||
      parsedLng < -180 ||
      parsedLng > 180
    ) {
      const message =
        'La longitud debe ser un valor numérico entre -180 y 180.';
      setError(message);
      toast.error(message);
      return;
    }

    setIsSubmitting(true);

    // NumericFormat.value entrega un string numérico estandarizado con punto decimal.
    const coordinates = {
      latitude: parsedLat,
      longitude: parsedLng,
    };

    try {
      if (isEditMode && stationId) {
        await apiClient.patch(`stations/${stationId}`, {
          name: name.trim() || null,
          description: description.trim() || null,
          coordinates,
          status,
        });
        toast.success('Estación actualizada.');
      } else {
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
    return (
      <div className="content-container" style={{ maxWidth: '860px' }}>
        <div className="card card-body" role="status">
          <p className="subtitle">Cargando estación...</p>
        </div>
      </div>
    );
  }

  return (
    <main className="content-container" style={{ maxWidth: '860px' }}>
      <header className="page-head">
        <div>
          <p className="eyebrow">Estaciones</p>
          <h1>{isEditMode ? 'Editar estación' : 'Registrar estación'}</h1>
          <p className="subtitle">
            {isEditMode
              ? 'Actualiza los metadatos operativos y las coordenadas geográficas WGS84 de la estación.'
              : 'Registra un nuevo punto de muestreo limnológico con sus coordenadas geográficas WGS84.'}
          </p>
        </div>
        <div className="head-actions">
          <Link className="btn btn-secondary" to={`/lakes/${lakeId}`}>
            Volver al lago
          </Link>
        </div>
      </header>

      <form
        className="card"
        onSubmit={(event) => void handleSubmit(event)}
      >
        <div className="card-head">
          <div>
            <h2>Datos de la Estación</h2>
            <p className="card-note">
              Los campos numéricos aceptan coma o punto decimal y se normalizan automáticamente.
            </p>
          </div>
          {isEditMode && code && <span className="code-pill">{code}</span>}
        </div>

        <div
          className="card-body"
          style={{ display: 'grid', gap: '18px' }}
        >
          {error && (
            <div className="status-banner danger" role="alert">
              <span>
                <span aria-hidden="true">⚠️</span> {error}
              </span>
            </div>
          )}

          <div className="grid grid-2">
            {!isEditMode && (
              <label className="label" htmlFor="station-code">
                Código
                <input
                  id="station-code"
                  className="control"
                  style={{ fontFamily: 'var(--mono)' }}
                  placeholder="Ej: EST-VIL-01"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  required
                />
              </label>
            )}

            <label className="label" htmlFor="station-name">
              Nombre
              <input
                id="station-name"
                className="control"
                placeholder="Ej: Estación Bahía Norte"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
              />
            </label>

            {isEditMode && (
              <label className="label" htmlFor="station-status">
                Estado
                <select
                  id="station-status"
                  className="control"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  <option value="active">Activa</option>
                  <option value="inactive">Inactiva</option>
                </select>
              </label>
            )}
          </div>

          <label className="label" htmlFor="station-description">
            Descripción
            <textarea
              id="station-description"
              className="control"
              placeholder="Referencia de ubicación, profundidad o observaciones de acceso..."
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
            />
          </label>

          <fieldset
            style={{
              margin: 0,
              padding: '16px',
              border: '1px solid var(--line)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--ice)',
            }}
          >
            <legend
              style={{
                padding: '0 6px',
                color: 'var(--navy)',
                fontSize: '11.5px',
                fontWeight: 750,
              }}
            >
              Coordenadas Geográficas (WGS84)
            </legend>

            <div className="grid grid-2">
              <label className="label" htmlFor="station-latitude">
                Latitud
                <NumericFormat
                  id="station-latitude"
                  className="control"
                  style={{ fontFamily: 'var(--mono)' }}
                  placeholder={`Ej: -39${decimalSeparator}2857`}
                  inputMode="decimal"
                  value={latitude}
                  onValueChange={(values) => setLatitude(values.value)}
                  allowedDecimalSeparators={[',', '.']}
                  decimalSeparator={decimalSeparator}
                  allowNegative={true}
                  required
                />
                <span className="card-note">Rango válido: -90 a 90</span>
              </label>

              <label className="label" htmlFor="station-longitude">
                Longitud
                <NumericFormat
                  id="station-longitude"
                  className="control"
                  style={{ fontFamily: 'var(--mono)' }}
                  placeholder={`Ej: -72${decimalSeparator}2279`}
                  inputMode="decimal"
                  value={longitude}
                  onValueChange={(values) => setLongitude(values.value)}
                  allowedDecimalSeparators={[',', '.']}
                  decimalSeparator={decimalSeparator}
                  allowNegative={true}
                  required
                />
                <span className="card-note">Rango válido: -180 a 180</span>
              </label>
            </div>
          </fieldset>

          <div
            className="head-actions"
            style={{
              justifyContent: 'flex-end',
              paddingTop: '6px',
              borderTop: '1px solid var(--line)',
            }}
          >
            <button
              className="btn btn-primary"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? 'Guardando...'
                : isEditMode
                  ? 'Guardar cambios'
                  : 'Registrar estación'}
            </button>
          </div>
        </div>
      </form>
    </main>
  );
}



