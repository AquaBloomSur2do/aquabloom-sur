// Lightweight fetch-based API client for Vite + TypeScript

const BASE_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/g, '');

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD';

export interface RequestOptions {
  method?: HttpMethod;
  token?: string;
  headers?: Record<string, string>;
  body?: unknown;
  signal?: AbortSignal;
}

export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string | null;
}

async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
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

  const res = await fetch(url, init);

  if (!res.ok) {
    const data = await res.json().catch(() => null);

    if (data && data.code && data.message) {
      return Promise.reject(data);
    }

    const errorObj: ApiError = {
      code: `HTTP_ERROR_${res.status}`,
      message: 'Error inesperado al consultar la API',
      details: data || res.statusText,
      request_id: null,
    };

    return Promise.reject(errorObj);
  }

  if (res.status === 204) {
    return {} as T;
  }

  const contentType = res.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    const data = await res.json().catch(() => null);
    return data as T;
  }

  const text = await res.text().catch(() => null);
  return (text as unknown) as T;
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
};

export default apiClient;
