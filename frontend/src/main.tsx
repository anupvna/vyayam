import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Fonts are bundled with the app (not loaded from Google), so they work offline.
import "@fontsource/marcellus/400.css";
import "@fontsource-variable/instrument-sans";

import { App } from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
