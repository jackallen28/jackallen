// Playwright drives the real web app against a real server (dev mode, a
// fresh data folder, its own port). Run: npm run e2e
import { defineConfig } from "@playwright/test";

const PORT = 8543;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `https://localhost:${PORT}`,
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: {
    command: `node tests/e2e/fresh-data.js && go run ./cmd/circuitpath-server -dev -data test-results/e2e-data -https :${PORT} -http off`,
    url: `https://localhost:${PORT}/api/info`,
    ignoreHTTPSErrors: true,
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
