import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // During development the FastAPI backend runs on :8787.
    proxy: { "/api": "http://localhost:8899" },
  },
});
