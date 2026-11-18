import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 45_000,
  expect: {
    timeout: 20_000,
  },
  retries: 0,
  use: {
    baseURL: process.env.QA_BASE_URL || "http://127.0.0.1:3001",
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: "only-on-failure",
  },
});
