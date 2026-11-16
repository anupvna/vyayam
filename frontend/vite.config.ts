// Vite builds the React app. The PWA plugin generates the web app manifest (name,
// icons, colours, used when you "Add to Home Screen") and a service worker that
// caches the app shell so it opens with no connection.
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate", // new versions install themselves on next open
      includeAssets: ["icons/apple-touch-icon.png"],
      manifest: {
        name: "Vyayam",
        short_name: "Vyayam",
        description: "Your personal gym coach",
        theme_color: "#141830",
        background_color: "#141830",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "icons/maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // Everything the app needs to open with no connection, fonts and icons included.
        // (Screen data is saved separately, per user: see src/offline/.)
        globPatterns: ["**/*.{js,css,html,woff2,png,svg,webmanifest}"],
        // Any page URL (e.g. /today) opens the cached app; API calls never use this.
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
  ],
  // The Progress tab's chart chunk (~190 KB gzipped) is lazy-loaded, so it doesn't
  // slow the first screen. Raise the warning threshold to match.
  build: { chunkSizeWarningLimit: 700 },
  server: {
    // In dev, the browser talks only to Vite (5173), which forwards /api to FastAPI.
    // Same origin means cookies just work, with no CORS setup.
    proxy: { "/api": "http://localhost:8000" },
  },
  test: { environment: "node" },
});
