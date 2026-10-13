import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Relative URLs keep the site working from any GitHub Pages repository path.
  base: './',
});
