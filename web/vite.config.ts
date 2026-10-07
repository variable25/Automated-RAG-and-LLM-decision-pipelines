import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev, /api is forwarded to `uvicorn rag_pipeline.api:app` on :8000.
// In production FastAPI serves the built files itself, so no proxy is needed.
export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 800 }, // Recharts is most of the bundle
  server: { proxy: { "/api": "http://localhost:8000" } },
});
