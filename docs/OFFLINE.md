# Working offline

Gyms often have no signal. Vyayam is built so a workout never depends on one.

## What works with no connection

| | Offline |
|---|---|
| Opening the app | Yes. The app itself (code, fonts, icons) is stored by the service worker. |
| Today's workout, plan, library, progress | Yes, as last loaded on this phone. Tomorrow's workout is saved in advance whenever Today opens online. |
| Logging and undoing sets | Yes, saved on the phone and synced later. |
| Daily check-in | Yes. Red flags still stop training right away; the rest of the advice arrives after syncing. |
| Weigh-ins, measurements, favorites | Yes, synced later. |
| Changing the plan (skip, swap, split), gyms, profile | No. These need the server to decide, so the app says a connection is needed. |
| Signing in or out | No. |

A banner at the top shows the state: offline, how many changes are waiting, syncing,
or "All changes synced".

## How it works

- **Saved screens.** Every screen's data is saved in IndexedDB (`src/offline/store.ts`)
  each time it loads. With no connection, the saved copy is shown.
- **Outbox.** A change that can wait (`src/offline/queue.ts` lists them) goes into an
  outbox when the network is down, or when older changes are still waiting, so the order
  is kept. Two changes to the same thing merge: undoing a set that never left the phone
  removes both; only the latest weigh-in for a day is kept.
- **Waiting changes stay visible.** Today's workout shows waiting sets and check-ins on
  top of whatever the server returned, so nothing seems to vanish.
- **Sync** (`src/offline/sync.ts`) runs when the connection returns, when the app comes
  back to the foreground, and every 30 seconds while anything is waiting. It sends one
  change at a time, in order, and stops at the first network failure.
- **Safe to send twice.** Every set has an id made on the phone, check-ins and weigh-ins
  overwrite the day's value, and undo deletes by id. A change that reached the server
  but lost its reply is simply sent again with no duplicates.
- **Server refusals.** If the server rejects a change (for example, invalid data), it's
  dropped so the rest can sync, and the banner says what happened. Server errors (5xx)
  and expired sessions keep the change for later.
- **A weak signal** counts as offline after 10 seconds.

## Privacy

Saved screens and waiting changes are kept per user and deleted on logout. If changes
haven't synced, logout asks first. To open offline, the app remembers only the last
user's id and email in local storage, never the session token or CSRF token.

## Testing it

In Chrome DevTools: Application → Service workers (check it's active), then Network →
Offline. Reload, log some sets, go back online and watch the banner.
