/**
 * Server-side API client.
 *
 * Every call from a React Server Component goes through here. The bearer token
 * is attached server side and never returned to the browser.
 *
 * `ApiError.message` is already the human-readable sentence the backend
 * produced. The backend's uniform envelope is `{ error: { message, code } }`,
 * so nothing here invents copy.
 */

import { readAccessToken } from "./session";
import type { ApiError } from "./types";

const FALLBACK_API_URL = "http://localhost:8000";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string | undefined;
  /**
   * The backend's structured payload, kept.
   *
   * It used to be dropped here, and that meant a 422 arrived with a sentence
   * that named no field: "Revise los datos" with nothing to point at. The API
   * already sends `details.errors` as a list of `{loc, msg}`, which is exactly
   * enough to put the message under the input it belongs to.
   */
  readonly details: unknown;

  constructor(error: ApiError) {
    super(error.message);
    this.name = "ApiRequestError";
    this.status = error.status;
    this.code = error.code;
    this.details = error.details;
  }

  /** True when the caller is authenticated but not allowed. */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  /** True when the resource is hidden rather than refused. */
  get isNotFound(): boolean {
    return this.status === 404;
  }
}

export class ApiNotAuthenticated extends Error {
  constructor() {
    super("Sesión no iniciada");
    this.name = "ApiNotAuthenticated";
  }
}

export function apiBaseUrl(): string {
  return (process.env.API_INTERNAL_URL ?? FALLBACK_API_URL).replace(/\/+$/, "");
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  /** Query parameters. `undefined` and `null` entries are dropped. */
  query?: Record<string, string | number | boolean | undefined | null>;
  /** Send no credential. Used by login. */
  anonymous?: boolean;
  signal?: AbortSignal;
  /** Absolute URL, for binary downloads that must stream through. */
  raw?: boolean;
};
function buildUrl(path: string, query: RequestOptions["query"]): string {
  const url = new URL(`${apiBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    url.searchParams.set(key, String(value));
  }
  return url.toString();
}

async function readError(response: Response): Promise<ApiError> {
  let message = `Error ${response.status}`;
  let code: string | undefined;
  let details: unknown;

  try {
    const payload = (await response.json()) as {
      detail?: unknown;
      error?: { message?: string; code?: string; details?: unknown };
    };
    if (payload?.error?.message) {
      message = payload.error.message;
      code = payload.error.code;
      details = payload.error.details;
    } else if (typeof payload?.detail === "string") {
      message = payload.detail;
    } else if (payload?.detail) {
      message = "Some requested data is invalid.";
      details = payload.detail;
    }
  } catch {
    // A non-JSON body means something upstream answered instead of the API.
    // Keep the status-based message rather than inventing one.
  }

  return { status: response.status, message, code, details };
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, query, anonymous = false, signal } = options;

  const headers: Record<string, string> = { Accept: "application/json" };

  /*
    A `FormData` body is passed through untouched and gets **no** Content-Type.

    That omission is the whole trick: the browser has to write the multipart
    boundary itself, and a header set here would either be wrong
    (`application/json`, which the backend would try to parse) or right-looking but
    still wrong (`multipart/form-data` without the generated boundary, which the
    backend cannot parse either). Everything else is JSON.
  */
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isFormData) headers["Content-Type"] = "application/json";

  if (!anonymous) {
    const token = await readAccessToken();
    if (!token) throw new ApiNotAuthenticated();
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    ...(body === undefined
      ? {}
      : { body: isFormData ? (body as FormData) : JSON.stringify(body) }),
    cache: "no-store",
    ...(signal ? { signal } : {}),
  });

  /*
   * No refresh here, deliberately.
   *
   * A Server Component cannot write cookies, so renewing the token inside this
   * function would retry with the very token it had just replaced. And because
   * the backend rotates the refresh token, that failed retry would spend the
   * renewed one and leave the user with no session at all. `proxy.ts` renews
   * before the render, which is the only place where the new token is visible
   * to the code that needs it.
   */
  if (!response.ok) throw new ApiRequestError(await readError(response));
  if (response.status === 204) return undefined as T;

  return (await response.json()) as T;
}

/**
 * Fetch and fall back to a default.
 *
 * Used for the blocks a page can render without. A portal with no cases must
 * show an empty state, not an error page: absence of data is not a failure.
 */
export async function apiFetchOr<T>(
  fallback: T,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  try {
    return await apiFetch<T>(path, options);
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) throw error;
    return fallback;
  }
}
