import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Every API surface the app touches is proxied to the FastAPI dev server.
const API = process.env.JIDOKA_API ?? "http://localhost:8099";

export default defineConfig({
  plugins: [react()],
  server: {
    // Pinned, not vite's default 5173: playwright.config.ts and the e2e specs address this port,
    // and a default that drifts means the browser walk silently tests nothing.
    port: 5273,
    strictPort: true,
    proxy: Object.fromEntries(
      ["/engagements", "/health", "/auth", "/schema", "/openapi.json"].map((p) => [p, API]),
    ),
  },
});
