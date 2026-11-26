import {defineConfig, loadEnv} from 'vite';
import {fileURLToPath} from 'node:url';

export default defineConfig(({mode}) => ({
  base: loadEnv(mode, process.cwd()).VITE_BASE || '/',
  server: {host: '127.0.0.1', port: 5174, strictPort: true},
  preview: {host: '127.0.0.1', port: 4174, strictPort: true},
  resolve: {alias: mode === 'e2e' ? [{
    find: /^(?:\.\.?\/)+auth\/provider\.ts$/,
    replacement: fileURLToPath(new URL('./src/auth/fake.ts', import.meta.url)),
  }] : []},
  build: {manifest: true, rollupOptions: {
    input: ['index.html', 'app/index.html'],
    // React libraries ship "use client" directives for server components; they are meaningless in a client-only build.
    onwarn(warning, warn) { if (warning.code !== 'MODULE_LEVEL_DIRECTIVE') warn(warning); },
  }},
}));
