import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import vue from "@astrojs/vue";

export default defineConfig({
  integrations: [vue()],
  vite: {
    plugins: [tailwindcss()],
  },
  outDir: "dist",
  srcDir: "src",
  publicDir: "public",
});
