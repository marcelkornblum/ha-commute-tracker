import { defineConfig } from "vite";

export default defineConfig({
  build: {
    lib: {
      entry: "src/commute-tracker-card.ts",
      formats: ["es"],
      fileName: () => "commute-tracker-card.js",
    },
    outDir: "dist",
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
  },
});
