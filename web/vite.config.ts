import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // FastAPI backend (see /backend/).  Start it with:
      //   .venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/files": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
})
