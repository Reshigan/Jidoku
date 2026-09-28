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
      // Kept in step with the Worker's API_PREFIXES, which src/routing.check.mjs asserts. A path
      // missing here is served the console's index.html with a 200, and the caller parses a web
      // page as JSON — the failure reads as a bug in the view, not as a missing route.
      ["/engagements", "/portfolio", "/health", "/auth", "/schema", "/openapi.json"].map((p) => [p, API]),
    ),
  },
});
