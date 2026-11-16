// Progress tab: Body, Training and Photos. This page (and the chart library) is
// loaded only when opened, so the rest of the app stays quick on phones.
import { useEffect, useState } from "react";
import { Navigate } from "react-router";

import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { TabBar } from "../components/TabBar";
import { localISO } from "../plan";
import { BodySection } from "../progress/BodySection";
import { PhotosSection } from "../progress/PhotosSection";
import { TrainingSection } from "../progress/TrainingSection";
import type { Catalog, Profile } from "../types";

type Tab = "body" | "training" | "photos";

export default function ProgressPage() {
  const today = localISO();
  const { state } = useAuth();
  const [tab, setTab] = useState<Tab>("body");
  const [profile, setProfile] = useState<Profile | null | "missing">(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    Promise.all([api<Profile>("/profile"), api<Catalog>("/catalog")])
      .then(([p, c]) => {
        setProfile(p);
        setCatalog(c);
      })
      .catch((err) => (err instanceof ApiError && err.status === 404 ? setProfile("missing") : setError(true)));
  }, []);

  if (profile === "missing") return <Navigate to="/onboarding" replace />;
  if (error) return <div className="splash">Couldn't load. Check your connection and refresh.</div>;
  if (!profile || !catalog || state.status !== "authenticated") return <div className="splash">Loading…</div>;

  return (
    <>
      <main className="page">
        <header className="page-head">
          <div>
            <p className="greeting">How it's going</p>
            <h1>Progress</h1>
          </div>
        </header>
        <div className="segmented" role="tablist" aria-label="Progress sections">
          {(["body", "training", "photos"] as const).map((t) => (
            <button key={t} type="button" role="tab" aria-selected={tab === t} aria-pressed={tab === t} onClick={() => setTab(t)}>
              {t === "body" ? "Body" : t === "training" ? "Training" : "Photos"}
            </button>
          ))}
        </div>
        {tab === "body" && <BodySection today={today} profile={profile} />}
        {tab === "training" && <TrainingSection today={today} profile={profile} catalog={catalog} />}
        {tab === "photos" && <PhotosSection today={today} userId={state.user.id} />}
      </main>
      <TabBar />
    </>
  );
}
