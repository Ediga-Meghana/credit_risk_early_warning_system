const BASE = import.meta.env.VITE_API_URL || "";
export const tokenStore = { get: () => localStorage.getItem("token"), set: (t: string) => localStorage.setItem("token", t), clear: () => localStorage.removeItem("token") };
export class ApiError extends Error { status: number; constructor(m: string, s: number) { super(m); this.status = s; } }
const MSG: Record<number, string> = { 400: "The request was invalid.", 401: "Your session has expired. Please sign in again.", 403: "Access denied.", 404: "The requested item was not found.", 409: "This item already exists.", 422: "Some values require review.", 429: "Too many requests. Please try again shortly.", 500: "A server error occurred. Please try again." };
export async function api<T = any>(path: string, opts: RequestInit & { json?: any; raw?: boolean } = {}): Promise<T> {
  const headers: any = { ...(opts.headers || {}) }; const t = tokenStore.get(); if (t) headers.Authorization = `Bearer ${t}`;
  let body = opts.body; if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
  let r: Response; try { r = await fetch(BASE + path, { ...opts, headers, body }); } catch { throw new ApiError("Unable to reach the server.", 0); }
  if (r.status === 401 && !path.includes("/auth/login")) { tokenStore.clear(); window.dispatchEvent(new Event("auth:expired")); }
  if (!r.ok) { let d = ""; try { const j = await r.json(); d = typeof j.detail === "string" ? j.detail : ""; } catch {} throw new ApiError(d || MSG[r.status] || "Request failed.", r.status); }
  if (opts.raw) return r as any;
  return r.json();
}
export async function download(path: string, name: string) {
  const r: Response = await api(path, { raw: true }); const b = await r.blob(); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = name; a.click();
}
