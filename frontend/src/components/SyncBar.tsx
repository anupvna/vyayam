// A slim banner at the top: offline, changes waiting, syncing, or a change the
// server refused. Hidden when everything is in sync.
import { useSyncExternalStore } from "react";

import { dismissFailed, getStatus, subscribe } from "../offline/status";

const changes = (n: number) => `${n} ${n === 1 ? "change" : "changes"}`;

export function SyncBar() {
  const s = useSyncExternalStore(subscribe, getStatus);

  if (s.failed.length)
    return (
      <div className="syncbar warn" role="alert">
        <span>
          {changes(s.failed.length)} couldn't be saved: {s.failed[0].message}
        </span>
        <button type="button" className="link small" onClick={dismissFailed}>
          OK
        </button>
      </div>
    );
  if (!s.online)
    return (
      <div className="syncbar offline" role="status">
        <i className="dot" aria-hidden="true" />
        <span>
          Offline.{" "}
          {s.pending
            ? `${changes(s.pending)} saved on this phone. They'll sync when you're back online.`
            : "Showing what's saved on this phone."}
        </span>
      </div>
    );
  if (s.pending)
    return (
      <div className="syncbar" role="status">
        <span>{s.syncing ? `Syncing ${changes(s.pending)}…` : `${changes(s.pending)} waiting to sync.`}</span>
      </div>
    );
  if (s.justSynced)
    return (
      <div className="syncbar ok" role="status">
        <span>All changes synced.</span>
      </div>
    );
  return null;
}
