const API = '/api';

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: 'teacher' | 'student';
  timezone: string;
}

export interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

function getTokens() {
  return {
    access: localStorage.getItem('access') || '',
    refresh: localStorage.getItem('refresh') || '',
  };
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem('access', access);
  localStorage.setItem('refresh', refresh);
}

export function clearTokens() {
  localStorage.removeItem('access');
  localStorage.removeItem('refresh');
}

async function refreshAccess(): Promise<string | null> {
  const { refresh } = getTokens();
  if (!refresh) return null;
  const res = await fetch(`${API}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  setTokens(data.access, data.refresh);
  return data.access;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let { access } = getTokens();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (access) headers['Authorization'] = `Bearer ${access}`;

  let res = await fetch(`${API}${path}`, { ...options, headers });
  if (res.status === 401) {
    access = (await refreshAccess()) || '';
    if (access) {
      headers['Authorization'] = `Bearer ${access}`;
      res = await fetch(`${API}${path}`, { ...options, headers });
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: { message: res.statusText } }));
    throw new Error(err.error?.message || 'Request failed');
  }
  if (res.status === 204) return {} as T;
  return res.json();
}

export const authApi = {
  register: (data: object) => api<AuthResponse>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data: object) => api<AuthResponse>('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => api<User>('/auth/me'),
  logout: () => api('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh: getTokens().refresh }) }),
};

export function wsUrl(path: string): string {
  const { access } = getTokens();
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host;
  return `${proto}://${host}${path}?token=${access}`;
}
