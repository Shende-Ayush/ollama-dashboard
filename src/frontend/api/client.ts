import { getApiKey, getAuthHeaders } from "../common/auth";
export const API_BASE = import.meta.env.VITE_API_BASE || "/v1";
export const WS_BASE  = import.meta.env.VITE_WS_BASE  || `${location.protocol==="https:"?"wss":"ws"}://${location.host}/v1`;
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...getAuthHeaders(), ...(init.headers as Record<string,string>||{}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || "Request failed");
  }
  return res.json();
}
export const api = {
  get:    <T>(path: string)                => request<T>(path),
  post:   <T>(path: string, body?: unknown)  => request<T>(path,{ method:"POST",  body:body?JSON.stringify(body):undefined }),
  patch:  <T>(path: string, body?: unknown)  => request<T>(path,{ method:"PATCH", body:body?JSON.stringify(body):undefined }),
  delete: <T>(path: string)                => request<T>(path,{ method:"DELETE" }),
};
export function wsUrl(path: string): string {
  return `${WS_BASE}${path}?token=${encodeURIComponent(getApiKey())}`;
}
