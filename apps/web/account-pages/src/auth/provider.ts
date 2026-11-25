// Production broker wiring. `vite --mode e2e` aliases this module to ./fake.ts (see vite.config.ts);
// scripts/check-build.mjs refuses a production build that contains the fake.
import {createNeonAuth} from './neon.ts';
import type {AuthPort} from './port.ts';

export function createAuth(): AuthPort {
  const url = import.meta.env.VITE_NEON_AUTH_URL as string | undefined;
  if (!url) throw new Error('VITE_NEON_AUTH_URL is not set (the Neon Auth URL of your branch).');
  return createNeonAuth(url);
}
