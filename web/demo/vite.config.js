import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/v1": { target: "https://uttg.oxis.cc", changeOrigin: true } },
  },
  build: {
    target: "es2022",
    chunkSizeWarningLimit: 2100,
    rollupOptions: {
      output: { manualChunks: { globe: ["globe.gl"], orbit: ["satellite.js"] } },
    },
  },
});
