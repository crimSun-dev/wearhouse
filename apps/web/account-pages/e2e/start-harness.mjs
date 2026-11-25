// Starts e2e/harness.py with the v2 API's virtualenv (paths contain spaces: spawn, never a shell string).
import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const api = fileURLToPath(new URL('../../../api/', import.meta.url));
const py = [api + '.venv/Scripts/python.exe', api + '.venv/bin/python'].find(existsSync) ?? 'python';
const child = spawn(py, [fileURLToPath(new URL('./harness.py', import.meta.url))], {stdio: 'inherit'});
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => child.kill('SIGTERM'));
child.on('exit', code => process.exit(code ?? 0));
