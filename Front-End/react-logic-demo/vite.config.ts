import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// BUGFIX: o plugin era passado sem ser invocado ("plugins: [react]"), o que
// quebra o build do Vite. O correto é chamar react().
//
// base "./" permite servir o build em qualquer subcaminho (o Apache do projeto
// serve em http://localhost:8010/app/). O outDir pode ser sobrescrito pela
// variável VITE_OUT_DIR — usada pelo serviço de build do docker compose para
// emitir direto em Front-End/files/app (pasta servida pelo Apache).
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: process.env.VITE_OUT_DIR || "dist",
    emptyOutDir: true
  }
});
