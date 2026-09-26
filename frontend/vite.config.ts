import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development the dashboard calls the local API dev server (port 8000)
// via a proxy, so browser requests stay same-origin and avoid CORS friction.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
