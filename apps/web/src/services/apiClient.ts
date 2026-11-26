import { supabase } from '../lib/supabase';
import type { DatasetVersionPublication } from '../types/dataset';

// Lightweight fetch-based API client for Vite + TypeScript

const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:5000/api/v1')
  .replace(/\/+$/g, '');

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface RequestOptions {
  method?: HttpMethod;
  token?: string;
  headers?: Record<string, string>;
  body?: unknown;
  signal?: AbortSignal;
}

export interface HealthResponse {
  service: string;
  version: string;
  status: 'ok' | 'degraded' | string;
  database: Record<string, unknown>;
}

export interface ApiErrorDetails {
  message: string;
  status: number;
  code?: string;
  details?: unknown;
  correlationId?: string;
  isNetworkError?: boolean;
  isCancelled?: boolean;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;
  correlationId?: string;
  isNetworkError: boolean;
  isCancelled: boolean;

  constructor(payload: ApiErrorDetails) {
    super(payload.message);
    this.name = 'ApiError';
    this.status = payload.status;
    this.code = payload.code;
    this.details = payload.details;
    this.correlationId = payload.correlationId;
    this.isNetworkError = payload.isNetworkError ?? false;
    this.isCancelled = payload.isCancelled ?? false;
  }
}

function createApiError(
  code: string,
  message: string,
  status: number,
  overrides: Partial<ApiErrorDetails> = {}
): ApiError {
  return new ApiError({
    message,
    status,
    code,
    details: overrides.details,
    correlationId: overrides.correlationId,
    isNetworkError: overrides.isNetworkError ?? false,
    isCancelled: overrides.isCancelled ?? false,
  });
}

function createCorrelationId(): string | undefined {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID();
  }
  return undefined;
}

async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', token, headers = {}, body, signal } = options;
  const url = path.startsWith('http') ? path : `${BASE_URL}/${path.replace(/^\/+/, '')}`;

  const outgoingCorrelationId =
    headers['X-Correlation-ID'] ?? headers['X-Request-ID'] ?? createCorrelationId();

  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers,
  };

  if (outgoingCorrelationId) {
    defaultHeaders['X-Correlation-ID'] = outgoingCorrelationId;
  }

  // --- S2-044: INYECCIÓN DE TOKEN DINÁMICO ---
  let activeToken = token;
  if (!activeToken) {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
          activeToken = session.access_token;
      }
  }

  if (activeToken) {
    defaultHeaders['Authorization'] = `Bearer ${activeToken}`;
  }
  // ------------------------------------------

  const init: RequestInit = {
    method,
    headers: defaultHeaders,
    signal,
  };

  if (body !== undefined && method !== 'GET') {
    init.body = JSON.stringify(body);
  }

  let res: Response;

  try {
    res = await fetch(url, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw createApiError('REQUEST_CANCELLED', 'La solicitud fue cancelada', 0, {
        isCancelled: true,
      });
    }

    throw createApiError('NETWORK_ERROR', 'Error de red o servidor no disponible', 0, {
      isNetworkError: true,
      correlationId: outgoingCorrelationId,
      details: error instanceof Error ? error.message : String(error),
    });
  }

  const responseCorrelationId =
    res.headers.get('X-Correlation-ID') ?? res.headers.get('X-Request-ID') ?? outgoingCorrelationId;

  // --- S2-044: MANEJO DE REDIRECCIÓN CONTROLADA ---
  if (res.status === 401) {
      await supabase.auth.signOut();
      
      if (!window.location.pathname.includes('/login')) {
          window.location.replace('/login');
      }
      
      throw createApiError('UNAUTHORIZED', 'Sesión expirada o token inválido.', 401, {
        correlationId: responseCorrelationId,
      });
  }
  // ------------------------------------------------

  if (res.status === 204) {
    return {} as T;
  }

  const contentType = res.headers.get('content-type') ?? '';
  const isJsonResponse = contentType.includes('application/json');

  let responseText: string;

  try {
    responseText = await res.text();
  } catch (error) {
    throw createApiError('RESPONSE_READ_ERROR', 'No se pudo leer la respuesta del servidor', res.status, {
      correlationId: responseCorrelationId,
      details: error instanceof Error ? error.message : String(error),
    });
  }

  if (!res.ok) {
    let parsedErrorBody: unknown;

    if (isJsonResponse && responseText) {
      try {
        const data = JSON.parse(responseText) as Record<string, unknown>;
        parsedErrorBody = data;
        const codeValue = data.code ?? data.error;
        const messageValue = data.message ?? data.detail;

        if (typeof codeValue !== 'undefined' || typeof messageValue !== 'undefined') {
          throw createApiError(
            typeof codeValue === 'string' ? codeValue : `HTTP_ERROR_${res.status}`,
            typeof messageValue === 'string'
              ? messageValue
              : 'Error inesperado al consultar la API',
            res.status,
            {
              correlationId: responseCorrelationId,
              details: data,
            }
          );
        }
      } catch (parseError) {
        if (parseError instanceof ApiError) {
          throw parseError;
        }
      }
    }

    throw createApiError(`HTTP_ERROR_${res.status}`, 'Error inesperado al consultar la API', res.status, {
      correlationId: responseCorrelationId,
      details: isJsonResponse
        ? (parsedErrorBody ?? 'La respuesta de error no es un JSON válido')
        : responseText || res.statusText,
    });
  }

  if (!responseText) {
    return {} as T;
  }

  if (!isJsonResponse) {
    throw createApiError(
      'INVALID_RESPONSE_FORMAT',
      'La respuesta del servidor no es JSON válido',
      res.status,
      {
        correlationId: responseCorrelationId,
        details: responseText,
      }
    );
  }

  try {
    const data = JSON.parse(responseText) as T;
    return data;
  } catch (error) {
    throw createApiError('JSON_PARSE_ERROR', 'No se pudo parsear la respuesta JSON', res.status, {
      correlationId: responseCorrelationId,
      details: error instanceof Error ? error.message : String(error),
    });
  }
}

export const apiClient = {
  request,
  get: <T = unknown>(path: string, opts: Omit<RequestOptions, 'method'> = {}) =>
    request<T>(path, { ...opts, method: 'GET' }),
  post: <T = unknown>(path: string, body?: unknown, opts: Omit<RequestOptions, 'method' | 'body'> = {}) =>
    request<T>(path, { ...opts, method: 'POST', body }),
  put: <T = unknown>(path: string, body?: unknown, opts: Omit<RequestOptions, 'method' | 'body'> = {}) =>
    request<T>(path, { ...opts, method: 'PUT', body }),
  patch: <T = unknown>(path: string, body?: unknown, opts: Omit<RequestOptions, 'method' | 'body'> = {}) =>
    request<T>(path, { ...opts, method: 'PATCH', body }),
  del: <T = unknown>(path: string, opts: Omit<RequestOptions, 'method'> = {}) =>
    request<T>(path, { ...opts, method: 'DELETE' }),
  getHealth: (): Promise<HealthResponse> => apiClient.get<HealthResponse>('health'),
  publishDatasetVersion: (
    versionId: string
  ): Promise<DatasetVersionPublication> =>
    apiClient.post<DatasetVersionPublication>(
      `datasets/versions/${versionId}/publish`
    ),
};

export default apiClient;
