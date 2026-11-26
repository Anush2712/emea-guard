import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Demo mode (GitHub Pages) serves from /emea-guard/ and reads the static API snapshot.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    base: env.VITE_BASE_PATH || "/",
    server: { proxy: { "/api": "http://localhost:8000" } },
    build: { chunkSizeWarningLimit: 4000 },
    test: { environment: "node" },
  };
});
