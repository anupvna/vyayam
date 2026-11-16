// Progress photos live ONLY on this device, in IndexedDB. They are never uploaded.
// Each photo records the account it belongs to, so two people sharing a phone don't
// see each other's photos. The data model keeps a `blob` so an encrypted cloud
// backup could be added later without changing the screens.

export type Pose = "front" | "side" | "back";

export type Photo = {
  id: string;
  userId: string;
  day: string; // YYYY-MM-DD
  pose: Pose;
  blob: Blob;
  createdAt: number;
};

const DB_NAME = "vyayam-photos";
const STORE = "photos";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const store = req.result.createObjectStore(STORE, { keyPath: "id" });
      store.createIndex("userId", "userId");
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function done<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function addPhoto(photo: Photo): Promise<void> {
  const db = await open();
  await done(db.transaction(STORE, "readwrite").objectStore(STORE).put(photo));
  db.close();
}

/** All photos for one account, oldest first. */
export async function listPhotos(userId: string): Promise<Photo[]> {
  const db = await open();
  const all = await done(db.transaction(STORE).objectStore(STORE).index("userId").getAll(userId));
  db.close();
  return (all as Photo[]).sort((a, b) => a.day.localeCompare(b.day) || a.createdAt - b.createdAt);
}

export async function deletePhoto(id: string, userId: string): Promise<void> {
  const db = await open();
  const store = db.transaction(STORE, "readwrite").objectStore(STORE);
  const existing = (await done(store.get(id))) as Photo | undefined;
  if (existing && existing.userId === userId) await done(store.delete(id));
  db.close();
}

export const REMINDER_DAYS = 14;

/** Days since the last photo, or null if there are none. */
export function daysSinceLast(photos: Photo[], today: string): number | null {
  if (photos.length === 0) return null;
  const last = photos[photos.length - 1].day;
  return Math.round((Date.parse(today) - Date.parse(last)) / 86_400_000);
}

/** The two photos to compare by default for a pose: first and latest. */
export function defaultPair(photos: Photo[], pose: Pose): [Photo, Photo] | null {
  const p = photos.filter((x) => x.pose === pose);
  return p.length >= 2 ? [p[0], p[p.length - 1]] : null;
}

/** Shrink a camera photo (often 4000px+) to at most `max` px on its long side as
 * JPEG, to save space on the phone. Browser-only. */
export async function compressImage(file: Blob, max = 1600): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, max / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b ?? file), "image/jpeg", 0.85));
}

/** Ask the browser not to clear our storage under pressure (iOS Safari especially). */
export async function requestPersistence(): Promise<boolean> {
  try {
    return (await navigator.storage?.persist?.()) ?? false;
  } catch {
    return false;
  }
}
