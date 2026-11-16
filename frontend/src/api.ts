// One place for every call to the backend.
// - Sends cookies (the session) automatically: same origin, credentials "same-origin".
// - Adds the CSRF token header on anything that changes data (non-GET).
// - Turns error responses into an ApiError with a readable message.
// - Works offline: each screen's data is saved on the phone and used when there's no
//   connection, and safe changes (sets, check-ins, weigh-ins) wait in an outbox and
//   are sent later (see offline/sync.ts). Anything else says it needs a connection.
import { applyPending, isQueueable, merge } from "./offline/queue";
import { getStatus, notifyQueued, updateStatus } from "./offline/status";
import { getRead, listOutbox, saveRead, updateOutbox } from "./offline/store";

export class ApiError extends Error {
  constructor(
    public status: number, // 0 means no connection
    message: string,
  ) {
    super(message);
  }
}

/** The request never got an answer (offline, or the signal dropped). */
export class NetworkError extends Error {}

export const OFFLINE_NEEDS_CONNECTION = "You're offline. This needs a connection, so try again once you're back online.";
export const OFFLINE_NOT_SAVED = "You're offline, and this screen isn't saved on this phone yet.";

/** Returned in place of the server's answer when a change was saved to send later. */
export const QUEUED = Symbol("queued");

// Kept in memory only (not localStorage), so injected scripts can't read it from storage.
let csrfToken: string | null = null;
// Whose saved data and outbox to use. Set on login, and from the last session when offline.
let sessionUser: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}
export const hasCsrfToken = (): boolean => csrfToken !== null;

export function setSessionUser(userId: string | null): void {
  sessionUser = userId;
}
export const getSessionUser = (): string | null => sessionUser;

type ValidationIssue = { loc?: (string | number)[]; msg?: string };

export function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    // FastAPI validation errors: [{loc: ["body", "password"], msg: "..."}]
    return (detail as ValidationIssue[])
      .map((d) => {
        const field = d.loc?.[d.loc.length - 1];
        return field ? `${field}: ${d.msg}` : (d.msg ?? "");
      })
      .join("; ");
  }
  return fallback;
}

// A weak gym signal can hang a request for a long time; give up and use the offline path.
const TIMEOUT_MS = 10_000;

/** One HTTP request, no offline handling. Throws NetworkError or ApiError. */
export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: abort.signal,
    });
  } catch {
    throw new NetworkError("No connection");
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      // body wasn't JSON
    }
    throw new ApiError(res.status, errorMessage(detail, `Request failed (${res.status})`));
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

async function pendingFor(user: string) {
  try {
    return await listOutbox(user);
  } catch {
    return []; // storage unavailable (private browsing): behave like a plain online app
  }
}

// Sign-in calls are never saved: they're about this moment, and carry a CSRF token.
const savable = (path: string) => !path.startsWith("/auth/");

async function get<T>(path: string): Promise<T> {
  const user = sessionUser;
  try {
    const data = await request<T>("GET", path);
    if (!getStatus().online) updateStatus({ online: true });
    if (!user || !savable(path)) return data;
    saveRead(user, path, data).catch(() => undefined);
    return applyPending(path, data, await pendingFor(user));
  } catch (err) {
    if (!(err instanceof NetworkError)) throw err;
    updateStatus({ online: false });
    const saved = user && savable(path) ? await getRead(user, path).catch(() => undefined) : undefined;
    if (!user || !saved) throw new ApiError(0, savable(path) ? OFFLINE_NOT_SAVED : OFFLINE_NEEDS_CONNECTION);
    return applyPending(path, saved.data as T, await pendingFor(user));
  }
}

async function enqueue(user: string, method: "POST" | "PUT" | "DELETE", path: string, body: unknown) {
  const pending = await listOutbox(user);
  const { remove, add } = merge(pending, { userId: user, method, path, body, createdAt: Date.now() });
  await updateOutbox(remove, add);
  updateStatus({ pending: pending.length - remove.length + (add ? 1 : 0) });
  notifyQueued();
}

/**
 * Call the API. For changes that may wait (see offline/queue.ts), pass `offline`: what
 * to show if the change has to wait in the outbox (e.g. the set as typed, or QUEUED).
 */
export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown; offline?: () => T } = {},
): Promise<T> {
  const method = options.method ?? "GET";
  if (method === "GET") return get<T>(path);

  const user = sessionUser;
  if (user && options.offline && isQueueable(method, path)) {
    // If older changes are still waiting, this one goes behind them to keep the order.
    if ((await pendingFor(user)).length === 0) {
      try {
        return await request<T>(method, path, options.body);
      } catch (err) {
        if (!(err instanceof NetworkError)) throw err;
        updateStatus({ online: false });
      }
    }
    try {
      await enqueue(user, method, path, options.body);
    } catch {
      throw new ApiError(0, OFFLINE_NEEDS_CONNECTION); // couldn't save it on the phone either
    }
    return options.offline();
  }

  try {
    return await request<T>(method, path, options.body);
  } catch (err) {
    if (!(err instanceof NetworkError)) throw err;
    updateStatus({ online: false });
    throw new ApiError(0, OFFLINE_NEEDS_CONNECTION);
  }
}
