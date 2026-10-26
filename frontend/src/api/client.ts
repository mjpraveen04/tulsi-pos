/**
 * The single API client. Every call goes through here so the JWT is attached in
 * exactly one place and a 401 always means the same thing.
 */

const TOKEN_KEY = "tulsi.token";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Anything thrown by `api()` is an ApiError; this is the safe unwrap for `catch`. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string): void => localStorage.setItem(TOKEN_KEY, token),
  clear: (): void => localStorage.removeItem(TOKEN_KEY),
};

/** Called by the auth context so an expired shift token bounces to Login. */
let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

/** FastAPI validation errors arrive as a list of {loc, msg}. */
interface ValidationDetail {
  msg?: string;
}

function readDetail(payload: unknown, status: number): string {
  const detail = (payload as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return (detail as ValidationDetail[])
      .map((item) => item.msg?.replace(/^Value error, /, "") ?? "")
      .join(" ");
  }
  return `Something went wrong (${status}). Please try again.`;
}

export interface ApiOptions {
  method?: string;
  body?: unknown;
  form?: FormData;
  auth?: boolean;
}

/** Multipart upload — the browser sets its own Content-Type with the boundary. */
export async function apiUpload<T>(
  path: string,
  file: File,
  { method = "POST" }: { method?: string } = {},
): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  return api<T>(path, { method, form });
}

export async function api<T = unknown>(
  path: string,
  { method = "GET", body, form, auth = true }: ApiOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const token = tokenStore.get();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      body: form ?? (body === undefined ? undefined : JSON.stringify(body)),
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check the connection and try again.");
  }

  if (response.status === 401 && auth) {
    onUnauthorized();
  }

  const payload: unknown =
    response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(response.status, readDetail(payload, response.status));
  }
  return payload as T;
}
