import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
  // Required for containerized `vite preview` behind ACA ingress/custom domain.
  preview: {
    allowedHosts: [
      "diiacui.vendorlogic.io",
      ".azurecontainerapps.io",
    ],
  },
});
