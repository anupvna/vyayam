// Routes. Logged-out users only see the auth page; logged-in users never see it.
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import type { ReactElement } from "react";

import { AuthProvider, useAuth } from "./auth";
import { AuthPage } from "./pages/AuthPage";
import { HomePage } from "./pages/HomePage";

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
        <Routes>
          <Route path="/login" element={<Gate need="anonymous"><AuthPage /></Gate>} />
          <Route path="/" element={<Gate need="authenticated"><HomePage /></Gate>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
