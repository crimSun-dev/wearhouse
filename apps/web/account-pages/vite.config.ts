import {fileURLToPath} from 'node:url';
import {defineConfig} from 'vite';

// `--mode e2e` swaps the real Neon Auth client for a test fake (tokens from the local EdDSA test issuer).
// scripts/check-build.mjs fails any production build that contains the fake.
export default defineConfig(({mode}) => ({
  server: {host: '127.0.0.1', port: 5174, strictPort: true},
  preview: {host: '127.0.0.1', port: 4174, strictPort: true},
  resolve: {
    alias: mode === 'e2e'
      ? [{find: /^\.\/auth\/provider\.ts$/, replacement: fileURLToPath(new URL('./src/auth/fake.ts', import.meta.url))}]
      : [],
  },
}));
