// What the app keeps on this phone so it works without a connection (IndexedDB):
// - reads:  the last copy of each screen's data, so screens open with no signal
// - outbox: changes made while offline (sets, check-ins, weigh-ins), sent in order later
// Both are kept per user and deleted on logout.

export type Method = "POST" | "PUT" | "DELETE";

export type OutboxItem = {
  seq?: number; // assigned by IndexedDB, gives the order to send in
  userId: string;
  method: Method;
  path: string;
  body?: unknown;
  createdAt: number;
};

export type SavedRead = { key: string; userId: string; path: string; data: unknown; savedAt: number };

const DB_NAME = "vyayam-offline";
let dbPromise: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        db.createObjectStore("reads", { keyPath: "key" }).createIndex("userId", "userId");
        db.createObjectStore("outbox", { keyPath: "seq", autoIncrement: true }).createIndex("userId", "userId");
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    dbPromise.catch(() => (dbPromise = null));
  }
  return dbPromise;
}

/** For tests: forget the open connection (after swapping in a fresh fake IndexedDB). */
export function resetStoreForTests(): void {
  dbPromise = null;
}

function done(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

function result<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

const readKey = (userId: string, path: string) => `${userId}|${path}`;

export async function saveRead(userId: string, path: string, data: unknown): Promise<void> {
  const tx = (await open()).transaction("reads", "readwrite");
  tx.objectStore("reads").put({ key: readKey(userId, path), userId, path, data, savedAt: Date.now() } satisfies SavedRead);
  await done(tx);
}

export async function getRead(userId: string, path: string): Promise<SavedRead | undefined> {
  const tx = (await open()).transaction("reads");
  return (await result(tx.objectStore("reads").get(readKey(userId, path)))) as SavedRead | undefined;
}

export async function listOutbox(userId: string): Promise<OutboxItem[]> {
  const tx = (await open()).transaction("outbox");
  const items = (await result(tx.objectStore("outbox").index("userId").getAll(userId))) as OutboxItem[];
  return items.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0));
}

/** Remove some queued items and add one, in a single transaction (used to merge changes). */
export async function updateOutbox(remove: number[], add: OutboxItem | null): Promise<void> {
  const tx = (await open()).transaction("outbox", "readwrite");
  const store = tx.objectStore("outbox");
  for (const seq of remove) store.delete(seq);
  if (add) store.add(add);
  await done(tx);
}

export async function removeOutbox(seq: number): Promise<void> {
  await updateOutbox([seq], null);
}

/** Logout: delete this user's saved screens and unsent changes from this phone. */
export async function clearUser(userId: string): Promise<void> {
  const db = await open();
  const tx = db.transaction(["reads", "outbox"], "readwrite");
  for (const name of ["reads", "outbox"] as const) {
    const store = tx.objectStore(name);
    const keys = await result(store.index("userId").getAllKeys(userId));
    for (const k of keys) store.delete(k);
  }
  await done(tx);
}
