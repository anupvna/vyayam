// Shared sync status for the banner: online or not, how many changes are waiting,
// and any change the server refused. A tiny store that React reads with
// useSyncExternalStore.

export type FailedChange = { path: string; status: number; message: string };

export type SyncStatus = {
  online: boolean;
  pending: number;
  syncing: boolean;
  failed: FailedChange[];
  justSynced: boolean; // shows "All changes synced" briefly
};

let state: SyncStatus = {
  online: typeof navigator === "undefined" ? true : navigator.onLine,
  pending: 0,
  syncing: false,
  failed: [],
  justSynced: false,
};
const listeners = new Set<() => void>();

export const getStatus = (): SyncStatus => state;

export function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function updateStatus(patch: Partial<SyncStatus>): void {
  const next = { ...state, ...patch };
  if ((Object.keys(patch) as (keyof SyncStatus)[]).every((k) => next[k] === state[k])) return;
  state = next;
  listeners.forEach((fn) => fn());
}

export function dismissFailed(): void {
  updateStatus({ failed: [] });
}

// "Something was queued" -> the sync loop sends it as soon as it can.
const queuedListeners = new Set<() => void>();
export function onQueued(fn: () => void): () => void {
  queuedListeners.add(fn);
  return () => queuedListeners.delete(fn);
}
export function notifyQueued(): void {
  queuedListeners.forEach((fn) => fn());
}

// "synced" (changes reached the server: screens reload) and "signed-out" (the session
// ended while offline). Pages listen with syncEvents.addEventListener(...).
export const syncEvents = new EventTarget();
export const SYNCED_EVENT = "synced";
export const SIGNED_OUT_EVENT = "signed-out";
