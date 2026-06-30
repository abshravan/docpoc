import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// The Flask API runs on :5000; Vite proxies /api there in dev so the browser
// hits a single origin. EPL_API_TARGET can override the backend URL.
const apiTarget = process.env.EPL_API_TARGET || "http://localhost:5000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
    },
  },
  // Build into the location Flask serves in production (webapp picks it up).
  build: { outDir: "dist" },
});
