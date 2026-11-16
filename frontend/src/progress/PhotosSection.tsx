// Progress photos: stored only on this phone (IndexedDB), never uploaded.
// Reminders every 2 weeks, a pose guide with tips for consistent photos, and a
// side-by-side or slider comparison between two dates.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  REMINDER_DAYS,
  addPhoto,
  compressImage,
  daysSinceLast,
  defaultPair,
  deletePhoto,
  listPhotos,
  requestPersistence,
  type Photo,
  type Pose,
} from "../photos";

type Props = { today: string; userId: string };

const POSES: { id: Pose; label: string }[] = [
  { id: "front", label: "Front" },
  { id: "side", label: "Side" },
  { id: "back", label: "Back" },
];

function PoseGuide({ pose }: { pose: Pose }) {
  // A simple outline to line up with: feet hip-width, arms relaxed slightly away.
  const side = pose === "side";
  return (
    <svg viewBox="0 0 100 190" className="pose-guide" aria-hidden="true">
      <circle cx="50" cy="18" r="10" />
      {side ? (
        <path d="M46 30 Q40 60 44 92 L42 140 L44 178 M54 30 Q62 60 56 92 L58 140 L56 178 M50 40 L50 90" />
      ) : (
        <path d="M38 34 Q30 36 28 46 L22 98 M62 34 Q70 36 72 46 L78 98 M38 34 L40 92 L38 178 M62 34 L60 92 L62 178 M40 92 L60 92" />
      )}
    </svg>
  );
}

export function PhotosSection({ today, userId }: Props) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [pose, setPose] = useState<Pose>("front");
  const [adding, setAdding] = useState(false);
  const [mode, setMode] = useState<"side" | "slider">("slider");
  const [beforeId, setBeforeId] = useState<string | null>(null);
  const [afterId, setAfterId] = useState<string | null>(null);
  const [split, setSplit] = useState(50);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const reload = useCallback(async () => {
    try {
      setPhotos(await listPhotos(userId));
    } catch {
      setError("This browser can't store photos (private browsing?).");
    }
  }, [userId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Object URLs for display; revoked when photos change or the screen closes.
  useEffect(() => {
    const next = Object.fromEntries(photos.map((p) => [p.id, URL.createObjectURL(p.blob)]));
    setUrls(next);
    return () => Object.values(next).forEach((u) => URL.revokeObjectURL(u));
  }, [photos]);

  const ofPose = useMemo(() => photos.filter((p) => p.pose === pose), [photos, pose]);
  const pair = defaultPair(photos, pose);
  const before = ofPose.find((p) => p.id === beforeId) ?? pair?.[0];
  const after = ofPose.find((p) => p.id === afterId) ?? pair?.[1];
  const since = daysSinceLast(photos, today);

  async function onFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const blob = await compressImage(file);
      await addPhoto({ id: crypto.randomUUID(), userId, day: today, pose, blob, createdAt: Date.now() });
      await requestPersistence();
      setAdding(false);
      await reload();
    } catch {
      setError("Couldn't save that photo. Try again.");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function remove(p: Photo) {
    if (!window.confirm("Delete this photo from this phone? This can't be undone.")) return;
    await deletePhoto(p.id, userId);
    await reload();
  }

  return (
    <div className="stack-tight progress-section">
      <p className="privacy-note">
        Photos stay on this phone only. They're never uploaded. Use "Save a copy" for any you want to keep elsewhere.
      </p>

      {(since === null || since >= REMINDER_DAYS) && !adding && (
        <section className="card reminder">
          <h2>{since === null ? "Take your first progress photos" : "Time for progress photos"}</h2>
          <p className="muted">
            {since === null
              ? "Photos show changes the scale can't. Take front, side and back today, then every 2 weeks."
              : `It's been ${since} days. Same spot, same light, same time of day.`}
          </p>
          <button type="button" className="primary" onClick={() => setAdding(true)}>
            Take photos
          </button>
        </section>
      )}

      {adding ? (
        <section className="card">
          <div className="card-head">
            <h2>New photo</h2>
            <button type="button" className="link small" onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
          <div className="segmented" role="group" aria-label="Pose">
            {POSES.map((p) => (
              <button key={p.id} type="button" aria-pressed={pose === p.id} onClick={() => setPose(p.id)}>
                {p.label}
              </button>
            ))}
          </div>
          <div className="pose-row">
            <PoseGuide pose={pose} />
            <ul className="tips">
              <li>Same spot and light every time (a window to your side works well).</li>
              <li>Same time of day, ideally in the morning.</li>
              <li>Phone at chest height, about 2 m (6 ft) away, or use a timer.</li>
              <li>Stand relaxed, feet hip-width, arms slightly away from your body.</li>
            </ul>
          </div>
          <input
            ref={input}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={(e) => void onFile(e.target.files?.[0])}
          />
          <button type="button" className="primary" disabled={busy} onClick={() => input.current?.click()}>
            {busy ? "Saving…" : `Take or choose ${pose} photo`}
          </button>
        </section>
      ) : (
        since !== null &&
        since < REMINDER_DAYS && (
          <button type="button" className="secondary" onClick={() => setAdding(true)}>
            Add a photo
          </button>
        )
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {photos.length > 0 && (
        <section className="card">
          <div className="card-head">
            <h2>Compare</h2>
            <div className="segmented small-seg" role="group" aria-label="Comparison style">
              <button type="button" aria-pressed={mode === "slider"} onClick={() => setMode("slider")}>
                Slider
              </button>
              <button type="button" aria-pressed={mode === "side"} onClick={() => setMode("side")}>
                Side by side
              </button>
            </div>
          </div>
          <div className="segmented" role="group" aria-label="Pose to compare">
            {POSES.map((p) => (
              <button key={p.id} type="button" aria-pressed={pose === p.id} onClick={() => setPose(p.id)}>
                {p.label}
              </button>
            ))}
          </div>
          {before && after && before.id !== after.id ? (
            <>
              <div className="two">
                <label>
                  <span className="hint">Before</span>
                  <select className="select" value={before.id} onChange={(e) => setBeforeId(e.target.value)}>
                    {ofPose.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.day}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span className="hint">After</span>
                  <select className="select" value={after.id} onChange={(e) => setAfterId(e.target.value)}>
                    {ofPose.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.day}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {mode === "side" ? (
                <div className="compare-side">
                  <figure>
                    <img src={urls[before.id]} alt={`${pose} photo from ${before.day}`} />
                    <figcaption>{before.day}</figcaption>
                  </figure>
                  <figure>
                    <img src={urls[after.id]} alt={`${pose} photo from ${after.day}`} />
                    <figcaption>{after.day}</figcaption>
                  </figure>
                </div>
              ) : (
                <div className="compare-slider">
                  <img src={urls[before.id]} alt={`${pose} photo from ${before.day}`} />
                  <img
                    src={urls[after.id]}
                    alt={`${pose} photo from ${after.day}`}
                    style={{ clipPath: `inset(0 0 0 ${split}%)` }}
                  />
                  <span className="slider-line" style={{ left: `${split}%` }} />
                  <span className="slider-tag left">{before.day}</span>
                  <span className="slider-tag right">{after.day}</span>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={split}
                    aria-label="Drag to compare"
                    onChange={(e) => setSplit(Number(e.target.value))}
                  />
                </div>
              )}
            </>
          ) : (
            <p className="muted">Take a second {pose} photo on another day to compare.</p>
          )}
        </section>
      )}

      {photos.length > 0 && (
        <section className="card">
          <h2>All photos</h2>
          <div className="photo-grid">
            {[...photos].reverse().map((p) => (
              <figure key={p.id}>
                <img src={urls[p.id]} alt={`${p.pose} photo from ${p.day}`} loading="lazy" />
                <figcaption>
                  {p.day}, {p.pose}
                  <span className="photo-actions">
                    <a className="link small" href={urls[p.id]} download={`vyayam-${p.day}-${p.pose}.jpg`}>
                      Save a copy
                    </a>
                    <button type="button" className="link small danger" onClick={() => remove(p)}>
                      Delete
                    </button>
                  </span>
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
