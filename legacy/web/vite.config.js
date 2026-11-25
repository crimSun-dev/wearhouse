import {fileURLToPath} from 'node:url';
import {defineConfig} from 'vite';

const target = 'http://127.0.0.1:8000';
const proxy = Object.fromEntries(['/api','/01','/docs','/openapi.json'].map(prefix=>[prefix,{target}]));
const entry = path=>fileURLToPath(new URL(path,import.meta.url));

export default defineConfig({
  base:process.env.VITE_BASE_PATH || '/',
  server:{host:'127.0.0.1',port:5173,strictPort:true,proxy},
  preview:{host:'127.0.0.1',proxy},
  build:{rollupOptions:{input:{landing:entry('./index.html'),app:entry('./app/index.html')}}},
});
