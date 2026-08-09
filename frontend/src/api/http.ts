import type { ApiErrorBody } from "./types";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | string | null;

  constructor(status: number, message: string, body: ApiErrorBody | string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }

  get code(): string | undefined {
    if (bodyIsObject(this.body) && typeof this.body.code === "string") return this.body.code;
    return undefined;
  }
}

function bodyIsObject(body: unknown): body is ApiErrorBody {
  return typeof body === "object" && body !== null && !Array.isArray(body);
}

export async function parseApiError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") {
      return new ApiError(res.status, body.detail, body.detail);
    }
    if (bodyIsObject(body.detail)) {
      const msg =
        typeof body.detail.message === "string"
          ? body.detail.message
          : typeof body.detail.code === "string"
            ? body.detail.code
            : res.statusText;
      return new ApiError(res.status, msg, body.detail);
    }
    if (Array.isArray(body.detail)) {
      const msg = body.detail.map((d: { msg?: string }) => d.msg ?? "Invalid input").join("; ");
      return new ApiError(res.status, msg, body.detail);
    }
    return new ApiError(res.status, res.statusText, body);
  } catch {
    return new ApiError(res.status, res.statusText, null);
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) throw await parseApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
