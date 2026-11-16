// Sends the outbox when the connection is back: in order, one at a time, stopping at
// the first sign the network is still down. Every queued change is safe to send twice
// (sets carry their own id; check-ins and weigh-ins overwrite), so a resend after a
// lost reply, or from two open tabs, never duplicates anything.
import { ApiError, NetworkError, getSessionUser, hasCsrfToken, request, setCsrfToken } from "../api";
import { SIGNED_OUT_EVENT, SYNCED_EVENT, onQueued, syncEvents, updateStatus } from "./status";
import { listOutbox, removeOutbox } from "./store";

type Session = { user: { id: string; email: string }; csrf_token: string };

const RETRY_MS = 30_000;

/** Ask the server who we are again (after starting offline): gets a fresh CSRF token. */
async function refreshSession(): Promise<"ok" | "offline" | "signed-out"> {
  try {
    const s = await request<Session>("GET", "/auth/me");
    setCsrfToken(s.csrf_token);
    return "ok";
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      syncEvents.dispatchEvent(new Event(SIGNED_OUT_EVENT));
      return "signed-out";
    }
    return "offline";
  }
}

let running: Promise<void> | null = null;

/** Send everything waiting. Safe to call any time; concurrent calls share one run. */
export function flush(): Promise<void> {
  running ??= send().finally(() => (running = null));
  return running;
}

async function send(): Promise<void> {
  const user = getSessionUser();
  if (!user) return;
  let items = await listOutbox(user).catch(() => []);
  updateStatus({ pending: items.length });
  if (!items.length) return;

  updateStatus({ syncing: true });
  let sent = 0;
  const failed: { path: string; status: number; message: string }[] = [];
  try {
    if (!hasCsrfToken() && (await refreshSession()) !== "ok") return;
    let retriedCsrf = false;
    while (items.length) {
      const item = items[0];
      let accepted = true;
      try {
        await request(item.method, item.path, item.body);
      } catch (err) {
        if (err instanceof NetworkError) return updateStatus({ online: false });
        if (!(err instanceof ApiError)) throw err;
        if (err.status === 403 && !retriedCsrf) {
          retriedCsrf = true; // the token may be stale: refresh once and retry
          if ((await refreshSession()) === "ok") continue;
          return;
        }
        if (err.status === 401 || err.status === 403 || err.status === 429 || err.status >= 500) return;
        // The server refused this change (e.g. a value out of range). Drop it so the
        // rest can sync, and tell the user.
        failed.push({ path: item.path, status: err.status, message: err.message });
        accepted = false;
      }
      await removeOutbox(item.seq as number);
      if (accepted) sent++;
      items = items.slice(1);
      updateStatus({ pending: items.length });
    }
    updateStatus({ online: true });
  } finally {
    updateStatus({ syncing: false, pending: items.length });
    if (failed.length) updateStatus({ failed });
    if (sent > 0) {
      syncEvents.dispatchEvent(new Event(SYNCED_EVENT));
      if (!items.length) {
        updateStatus({ justSynced: true });
        setTimeout(() => updateStatus({ justSynced: false }), 3000);
      }
    }
  }
}

/** Start syncing for the signed-in user. Returns a function that stops it. */
export function startSync(): () => void {
  const kick = () => void flush();
  const onVisible = () => document.visibilityState === "visible" && kick();
  const onOffline = () => updateStatus({ online: false });
  window.addEventListener("online", kick);
  window.addEventListener("offline", onOffline);
  document.addEventListener("visibilitychange", onVisible);
  const stopQueued = onQueued(kick);
  const timer = window.setInterval(kick, RETRY_MS);
  kick();
  return () => {
    window.removeEventListener("online", kick);
    window.removeEventListener("offline", onOffline);
    document.removeEventListener("visibilitychange", onVisible);
    stopQueued();
    window.clearInterval(timer);
  };
}
