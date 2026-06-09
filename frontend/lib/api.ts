const API_BASE =
  typeof window === "undefined"
    ? (process.env.INTERNAL_API_URL ?? "http://helpdesk-backend:8004")
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8004");

export function buildApiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

type FetchOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { body, ...rest } = options;
  const res = await fetch(buildApiUrl(path), {
    ...rest,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(rest.headers as Record<string, string>),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Não autenticado");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Erro desconhecido");
  }

  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, init?: RequestInit) => apiFetch<T>(path, { ...init, method: "GET" }),
  post: <T>(path: string, body: unknown, init?: RequestInit) =>
    apiFetch<T>(path, { ...init, method: "POST", body }),
  patch: <T>(path: string, body: unknown, init?: RequestInit) =>
    apiFetch<T>(path, { ...init, method: "PATCH", body }),
  del: <T>(path: string, init?: RequestInit) => apiFetch<T>(path, { ...init, method: "DELETE" }),
};
