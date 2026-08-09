import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./specs",
  timeout: 60_000,
  expect: {
    timeout: 10_000
  },
  fullyParallel: false,
  reporter: [
    ["list"],
    ["json", { outputFile: "../reports/playwright-results.json" }],
    ["html", { outputFolder: "../reports/playwright-html", open: "never" }]
  ],
  use: {
    baseURL: process.env.WEB_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
