import {spawn} from 'node:child_process';
import {existsSync, readdirSync, rmSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {build, preview, type PreviewServer} from 'vite';
import type {FullConfig} from '@playwright/test';

export default async function setup(config: FullConfig) {
  const origin = new URL(config.projects[0].use.baseURL!).origin;
  const port = process.env.E2E_API_PORT || '8199';
  const apiBase = 'http://127.0.0.1:' + port;
  const api = new URL('../../../api/', import.meta.url);
  const python = ['.venv/Scripts/python.exe', '.venv/bin/python']
    .map(path => fileURLToPath(new URL(path, api))).find(existsSync) ?? 'python';
  const harness = spawn(python, [fileURLToPath(new URL('harness.py', import.meta.url))], {
    stdio: ['pipe', 'inherit', 'inherit'],
    env: {...process.env, E2E_MANAGED: '1', E2E_PAGES_ORIGIN: origin},
  });
  const ended = new Promise<number | null>((resolve, reject) => {
    harness.once('error', reject);
    harness.once('exit', resolve);
  });
  let server: PreviewServer | undefined;
  async function close() {
    harness.stdin.end();
    if (server) await server.close();
    await ended;
  }
  try {
    const ready = async () => {
      for (let i = 0; i < 240; i++) {
        try {
          const response = await fetch(apiBase + '/api/v2/health', {signal: AbortSignal.timeout(500)});
          if (response.ok) return;
        } catch { /* The harness is still migrating. */ }
        if (harness.exitCode !== null) break;
        await delay(250);
      }
      throw new Error('The disposable API did not become ready.');
    };
    await Promise.race([ready(), ended.then(code => {throw new Error('Harness exited: ' + code);})]);
    // Each run builds into its own folder: on this repo's exFAT drive a just-deleted folder can stay locked for a
    // while, so emptying and reusing one output folder fails intermittently. Old runs are removed when possible, but
    // only runs older than two hours: another session's suite may be serving a recent one on its own ports right now.
    const started = Date.now();
    const outDir = `dist-test/run-${started}`;
    for (const old of existsSync('dist-test') ? readdirSync('dist-test') : []) {
      const at = Number(/^run-(\d+)$/.exec(old)?.[1]);
      if (!at || started - at < 2 * 3600_000) continue;
      try { rmSync(`dist-test/${old}`, {recursive: true, force: true}); } catch { /* still locked; next run */ }
    }
    await build({mode: 'e2e', build: {outDir, emptyOutDir: true}, define: {
      'import.meta.env.VITE_WEARHOUSE_API_BASE': JSON.stringify(apiBase + '/api/v2'),
      'import.meta.env.VITE_E2E_TOKEN_URL': JSON.stringify(apiBase + '/__e2e/token'),
    }});
    server = await preview({mode: 'e2e', build: {outDir},
      preview: {host: '127.0.0.1', port: Number(new URL(origin).port), strictPort: true}});
    return close;
  } catch (error) {
    await close();
    throw error;
  }
}
