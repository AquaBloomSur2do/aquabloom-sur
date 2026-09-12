// Lightweight fetch-based API client for Vite + TypeScript

const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1')
  .replace(/\/+$/g, '')
  .replace(/\/+/g, '/');

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface RequestOptions {
  method?: HttpMethod;
  token?: string;
  headers?: Record<string, string>;
  body?: any;
  signal?: AbortSignal;
}

export interface ApiErrorDetails {
  message: string;
  status: number;
  code?: string;
  details?: unknown;
  isNetworkError?: boolean;
  isCancelled?: boolean;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;
  isNetworkError: boolean;
  isCancelled: boolean;

  constructor(payload: ApiErrorDetails) {
    super(payload.message);
    this.name = 'ApiError';
    this.status = payload.status;
    this.code = payload.code;
    this.details = payload.details;
    this.isNetworkError = payload.isNetworkError ?? false;
    this.isCancelled = payload.isCancelled ?? false;
  }
}

function createApiError(code: string, message: string, status: number, overrides: Partial<ApiErrorDetails> = {}): ApiError {
  return new ApiError({
    message,
    status,
    code,
    details: overrides.details,
    isNetworkError: overrides.isNetworkError ?? false,
    isCancelled: overrides.isCancelled ?? false,
  });
}

async function request<T = any>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', token, headers = {}, body, signal } = options;
  const url = path.startsWith('http') ? path : `${BASE_URL}/${path.replace(/^\/+/, '')}`;

  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers,
  };

  if (token) {
    defaultHeaders['Authorization'] = `Bearer ${token}`;
  }

  const init: RequestInit = {
    method,
    headers: defaultHeaders,
    signal,
  };

  if (body !== undefined && method !== 'GET' && method !== 'HEAD') {
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
      details: error instanceof Error ? error.message : String(error),
    });
  }

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
      details: error instanceof Error ? error.message : String(error),
    });
  }

  if (!res.ok) {
    if (isJsonResponse && responseText) {
      try {
        const data = JSON.parse(responseText) as Record<string, unknown>;

        if (data && typeof data === 'object' && 'code' in data && 'message' in data) {
          throw createApiError(String(data.code), String(data.message), res.status, {
            details: data,
          });
        }
      } catch (parseError) {
        if (parseError instanceof ApiError) {
          throw parseError;
        }
      }
    }

    throw createApiError(`HTTP_ERROR_${res.status}`, 'Error inesperado al consultar la API', res.status, {
      details: isJsonResponse
        ? 'La respuesta de error no es un JSON válido'
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
        details: responseText,
      }
    );
  }

  try {
    const data = JSON.parse(responseText) as T;
    return data;
  } catch (error) {
    throw createApiError('JSON_PARSE_ERROR', 'No se pudo parsear la respuesta JSON', res.status, {
      details: error instanceof Error ? error.message : String(error),
    });
  }
}

export const apiClient = {
  request,
  get: <T = any>(path: string, opts: Omit<RequestOptions, 'method'> = {}) =>
    request<T>(path, { ...opts, method: 'GET' }),
  post: <T = any>(path: string, body?: any, opts: Omit<RequestOptions, 'method' | 'body'> = {}) =>
    request<T>(path, { ...opts, method: 'POST', body }),
  put: <T = any>(path: string, body?: any, opts: Omit<RequestOptions, 'method' | 'body'> = {}) =>
    request<T>(path, { ...opts, method: 'PUT', body }),
  patch: <T = any>(path: string, body?: any, opts: Omit<RequestOptions, 'method' | 'body'> = {}) =>
    request<T>(path, { ...opts, method: 'PATCH', body }),
  del: <T = any>(path: string, opts: Omit<RequestOptions, 'method'> = {}) =>
    request<T>(path, { ...opts, method: 'DELETE' }),
};

export default apiClient;
