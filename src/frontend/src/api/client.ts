// No-auth API client — no Authorization headers sent.
export const API_BASE = import.meta.env.VITE_API_BASE || "/api";
export const WS_BASE  = import.meta.env.VITE_WS_BASE  ||
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api`;

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers as Record<string, string> || {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  get:    <T>(path: string)                => request<T>(path),
  post:   <T>(path: string, body?: unknown)  => request<T>(path, { method: "POST",   body: body ? JSON.stringify(body) : undefined }),
  patch:  <T>(path: string, body?: unknown)  => request<T>(path, { method: "PATCH",  body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string)                => request<T>(path, { method: "DELETE" }),
};

// WebSocket URL — no token param needed
export function wsUrl(path: string): string {
  return `${WS_BASE}${path}`;
}
