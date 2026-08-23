/**
 * The single API client. Every call goes through here so the JWT is attached in
 * exactly one place and a 401 always means the same thing.
 */

const TOKEN_KEY = "tulsi.token";

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

/** Called by the auth context so an expired shift token bounces to Login. */
let onUnauthorized = () => {};
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

function readDetail(payload, status) {
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  // FastAPI validation errors arrive as a list of {loc, msg}.
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => item.msg?.replace(/^Value error, /, "")).join(" ");
  }
  return `Something went wrong (${status}). Please try again.`;
}

/** Multipart upload — the browser sets its own Content-Type with the boundary. */
export async function apiUpload(path, file, { method = "POST" } = {}) {
  const form = new FormData();
  form.append("file", file);
  return api(path, { method, form });
}

export async function api(path, { method = "GET", body, form, auth = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const token = tokenStore.get();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let response;
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

  const payload = response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(response.status, readDetail(payload, response.status));
  }
  return payload;
}
