import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 8_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.JIDOKA_WEB ?? "http://localhost:5273",
    viewport: { width: 1440, height: 950 },
    screenshot: "only-on-failure",
  },
  // Both servers, started by the test run itself. `reuseExistingServer` keeps a dev session's
  // already-running pair, so the same `npx playwright test` works locally and on a cold CI box.
  webServer: [
    {
      // `python` on CI (setup-python), the repo venv locally where it usually is not on PATH.
      command:
        `${process.env.JIDOKA_PYTHON ?? (process.env.CI ? "python" : "../../.venv/bin/python")}` +
        " -m uvicorn jidoka_api.main:app --port 8099 --app-dir ../../services/api/src",
      url: "http://localhost:8099/health",
      reuseExistingServer: !process.env.CI,
      env: { JIDOKA_DB_URL: "sqlite:///" + (process.env.JIDOKA_E2E_DB ?? "/tmp/jidoka-e2e.db") },
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5273",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
