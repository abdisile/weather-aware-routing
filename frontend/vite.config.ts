import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const root = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.join(root, "src"),
    },
  },
  optimizeDeps: {
    exclude: ["maplibre-gl"],
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
