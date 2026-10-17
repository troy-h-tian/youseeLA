import { defineConfig, devices } from '@playwright/test';

const PORT = 4173;

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}/`,
    trace: 'retain-on-failure',
  },
  // Measurements and journeys run against the production build, never the dev server.
  webServer: {
    command: `npm run build && npm run preview -- --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: `http://127.0.0.1:${PORT}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'journeys-desktop',
      testMatch: /journeys\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'journeys-mobile',
      testMatch: /journeys\.spec\.ts/,
      use: { ...devices['Pixel 7'] },
    },
    {
      name: 'scalability',
      testMatch: /scalability\.spec\.ts/,
      fullyParallel: false,
      workers: 1,
      timeout: 300_000,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
  ],
});
