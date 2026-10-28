import { api } from "./api";
export const auth = { login: (email: string, password: string) => api("/api/auth/login", { method: "POST", json: { email, password } }), requestSignupOtp: (email: string, full_name: string, password: string) => api("/api/auth/signup/request-otp", { method: "POST", json: { email, full_name, password } }), verifySignupOtp: (email: string, otp: string) => api("/api/auth/signup/verify-otp", { method: "POST", json: { email, otp } }), me: () => api("/api/auth/me"),
  changePassword: (current_password: string, new_password: string) => api("/api/auth/change-password", { method: "POST", json: { current_password, new_password } }) };
export const dashboard = { summary: () => api("/api/dashboard/summary"), distribution: () => api("/api/dashboard/risk-distribution"), recent: () => api("/api/dashboard/recent-assessments") };
export const companies = { list: (q = "", page = 1) => api(`/api/companies?q=${encodeURIComponent(q)}&page=${page}&size=50`), get: (id: any) => api(`/api/companies/${id}`), create: (j: any) => api("/api/companies", { method: "POST", json: j }) };
export const prediction = { features: () => api("/api/model/features"), assess: (company_id: number, values: any) => api("/api/assessments", { method: "POST", json: { company_id, values } }),
  get: (id: any) => api(`/api/assessments/${id}`), delete: (id: any) => api(`/api/assessments/${id}`, { method: "DELETE" }), history: (p: Record<string, any>) => api("/api/assessments?" + new URLSearchParams(Object.entries(p).filter(([, v]) => v !== "" && v != null).map(([k, v]) => [k, String(v)]) as any)),
  batch: (company_id: number, file: File) => { const f = new FormData(); f.append("file", file); return api(`/api/assessments/batch?company_id=${company_id}`, { method: "POST", body: f }); } };
export const model = { info: () => api("/api/model/info"), train: () => api("/api/admin/model/train", { method: "POST" }) };
export const assistant = { chat: (message: string, assessment_id?: number) => api("/api/assistant/chat", { method: "POST", json: { message, assessment_id } }) };
export const notifications = { list: () => api("/api/notifications"), readAll: () => api("/api/notifications/read-all", { method: "POST" }) };
export const admin = { users: () => api("/api/admin/users"), createUser: (j: any) => api("/api/admin/users", { method: "POST", json: j }), patchUser: (id: number, j: any) => api(`/api/admin/users/${id}`, { method: "PUT", json: j }),
  logs: (page: number) => api(`/api/admin/audit-logs?page=${page}&size=25`), thresholds: () => api("/api/settings/thresholds"), setThresholds: (j: any) => api("/api/admin/settings/thresholds", { method: "PUT", json: j }) };

export const yahoo = {
  search: (q: string) => api(`/api/yahoo/search?q=${encodeURIComponent(q)}`),
  company: (symbol: string) => api(`/api/yahoo/company/${encodeURIComponent(symbol)}`),
  assess: (symbol: string) => api("/api/yahoo/assess", { method: "POST", json: { symbol } }),
};

export const monitoring = {
  list: () => api("/api/monitoring/watchlist"),
  add: (symbol: string) => api("/api/monitoring/watchlist", { method: "POST", json: { symbol } }),
  check: () => api("/api/monitoring/check", { method: "POST" }),
  history: (id: number) => api(`/api/monitoring/watchlist/${id}/history`),
};
