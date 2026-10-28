import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    // Forzamos a Vite a no pre-empaquetar ni alterar el código de maplibre-gl
    // para evitar que se rompa la referencia interna a su Web Worker.
    exclude: ['maplibre-gl'],
  },
});