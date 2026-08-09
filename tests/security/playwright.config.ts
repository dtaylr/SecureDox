import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./specs",
  timeout: 60_000,
  fullyParallel: false,
  reporter: [
    ["list"],
    ["json", { outputFile: "../reports/security-playwright-results.json" }],
    ["html", { outputFolder: "../reports/security-playwright-html", open: "never" }]
  ],
  use: {
    baseURL: process.env.API_BASE_URL ?? "http://localhost:8000",
    trace: "retain-on-failure"
  }
});
