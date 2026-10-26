import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev (`npm run dev`) the API runs on :8000; in the container nginx proxies
// /api itself, so the built bundle only ever calls same-origin /api.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
      "/media": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
