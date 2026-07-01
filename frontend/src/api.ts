/** Thin typed fetch wrapper with bearer-token auth. */

let token: string | null = localStorage.getItem("rigbooks_token");

export function setToken(t: string | null) {
  token = t;
  if (t) localStorage.setItem("rigbooks_token", t);
  else localStorage.removeItem("rigbooks_token");
}

export function getToken() {
  return token;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.body && !(init.body instanceof FormData))
    headers["Content-Type"] = "application/json";
  const res = await fetch(path, { ...init, headers });
  if (res.status === 401 && !path.includes("/auth/")) {
    setToken(null);
    window.location.reload();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* keep statusText */ }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export const api = {
  get: <T = any>(path: string) => request<T>(path),
  post: <T = any>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T = any>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  del: <T = any>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T = any>(path: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<T>(path, { method: "POST", body: fd });
  },
  /** Authenticated file download (PDF/CSV exports). */
  download: async (path: string, filename: string) => {
    const res = await fetch(path, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, res.statusText);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
};

export const money = (v: number | undefined | null) =>
  (v ?? 0).toLocaleString("en-CA", { style: "currency", currency: "CAD" });

export const compactMoney = (v: number) =>
  Math.abs(v) >= 10000
    ? "$" + (v / 1000).toFixed(v % 1000 === 0 ? 0 : 1) + "K"
    : money(v);
