export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  if (typeof window !== "undefined" && !sessionStorage.getItem("csrf_token") && path !== "/auth/login") {
    try {
      const bootstrap = await fetch("/api/v1/auth/csrf", { credentials: "include" });
      if (bootstrap.ok) {
        const body = await bootstrap.json();
        if (body.csrf_token) sessionStorage.setItem("csrf_token", body.csrf_token);
      }
    } catch {
      /* brew-day remains usable via manual retry after login */
    }
  }
  const csrf = typeof window !== "undefined" ? sessionStorage.getItem("csrf_token") : null;
  const headers: Record<string, string> = {
    ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    ...(init?.headers as Record<string, string> | undefined),
  };
  const isForm = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!isForm && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  if (path === "/auth/login" && response.ok) {
    const body = await response.clone().json().catch(() => null);
    if (body?.csrf_token) sessionStorage.setItem("csrf_token", body.csrf_token);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    const detail = body.detail;
    let message = "Request failed";
    if (typeof detail === "string") message = detail;
    else if (Array.isArray(detail)) {
      message = detail
        .map((item: { msg?: string } | string) =>
          typeof item === "string" ? item : item?.msg ?? JSON.stringify(item),
        )
        .join("; ");
    } else if (detail && typeof detail === "object") {
      message = detail.message || detail.msg || JSON.stringify(detail);
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
