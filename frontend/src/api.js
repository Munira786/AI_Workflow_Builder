// api.js
// Small fetch wrapper for the backend API: base URL from env, bearer token, readable errors.

export const API_URL = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const TOKEN_KEY = 'awb_token';

export const tokenStorage = {
  get() {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      // Storage unavailable (private mode): the session just won't survive a reload.
    }
  },
};

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

let unauthorizedHandler = () => {};
export const onUnauthorized = (handler) => {
  unauthorizedHandler = handler;
};

const formatDetail = (detail) => {
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg}, ...]
    return detail.map((item) => item.msg?.replace(/^Value error, /, '') || String(item)).join('; ');
  }
  return typeof detail === 'string' ? detail : 'Request failed';
};

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {};
  const token = tokenStorage.get();
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload;
  if (form) {
    payload = new URLSearchParams(form);
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running?', 0);
  }

  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 401 && token) unauthorizedHandler();
    throw new ApiError(formatDetail(data.detail), response.status);
  }
  return data;
}

// Only the fields the backend needs; React Flow adds UI state (selected, dragging, ...) we skip.
export const serializeGraph = (nodes, edges) => ({
  nodes: nodes.map(({ id, type, position, data }) => ({ id, type, position, data })),
  edges: edges.map(({ id, source, target, sourceHandle, targetHandle, type, animated, style, markerEnd }) => ({
    id, source, target, sourceHandle, targetHandle, type, animated, style, markerEnd,
  })),
});
