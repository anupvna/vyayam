// Routes. Logged-out users only see the auth page; logged-in users never see it.
import { Suspense, lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import type { ReactElement } from "react";

import { AuthProvider, useAuth } from "./auth";
import { SyncBar } from "./components/SyncBar";
import { AuthPage } from "./pages/AuthPage";
import { ExercisePage } from "./pages/ExercisePage";
import { GymsPage } from "./pages/GymsPage";
import { HomePage } from "./pages/HomePage";
import { LibraryPage } from "./pages/LibraryPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { PlanPage } from "./pages/PlanPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SplitPage } from "./pages/SplitPage";

// Loaded on demand: the chart library is only needed on this tab.
const ProgressPage = lazy(() => import("./pages/ProgressPage"));

function Gate({ need, children }: { need: "authenticated" | "anonymous"; children: ReactElement }) {
  const { state } = useAuth();
  if (state.status === "loading") return <div className="splash">Loading…</div>;
  if (state.status !== need) return <Navigate to={need === "authenticated" ? "/login" : "/"} replace />;
  return children;
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <SyncBar />
        <Routes>
          <Route path="/login" element={<Gate need="anonymous"><AuthPage /></Gate>} />
          <Route path="/" element={<Gate need="authenticated"><HomePage /></Gate>} />
          <Route path="/onboarding" element={<Gate need="authenticated"><OnboardingPage /></Gate>} />
          <Route path="/gyms" element={<Gate need="authenticated"><GymsPage /></Gate>} />
          <Route path="/plan" element={<Gate need="authenticated"><PlanPage /></Gate>} />
          <Route path="/plan/split" element={<Gate need="authenticated"><SplitPage /></Gate>} />
          <Route
            path="/progress"
            element={
              <Gate need="authenticated">
                <Suspense fallback={<div className="splash">Loading…</div>}>
                  <ProgressPage />
                </Suspense>
              </Gate>
            }
          />
          <Route path="/library" element={<Gate need="authenticated"><LibraryPage /></Gate>} />
          <Route path="/exercises/:id" element={<Gate need="authenticated"><ExercisePage /></Gate>} />
          <Route path="/profile" element={<Gate need="authenticated"><ProfilePage /></Gate>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
