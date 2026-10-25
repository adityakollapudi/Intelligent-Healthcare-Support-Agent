import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // Port 5173 + host "localhost" match the backend's default CORS_ORIGINS.
  server: { port: 5173, strictPort: true, host: "localhost" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // Tests never touch a real backend: fetch is stubbed per test against this fake origin.
    env: { VITE_API_BASE_URL: "http://api.test/api/v1", VITE_API_TIMEOUT_MS: "2000" },
  },
});
