import { defineConfig } from "vite";
import fs from "node:fs";
import path from "node:path";

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
  plugins: [
    {
      name: "copy-to-custom-component",
      closeBundle() {
        const destDir = path.resolve(
          __dirname,
          "../custom_components/commute_tracker/frontend"
        );
        if (!fs.existsSync(destDir)) {
          fs.mkdirSync(destDir, { recursive: true });
        }
        fs.copyFileSync(
          path.resolve(__dirname, "dist/commute-tracker-card.js"),
          path.resolve(destDir, "commute-tracker-card.js")
        );
      },
    },
  ],
});
