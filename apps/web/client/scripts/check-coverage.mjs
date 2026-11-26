import ts from 'typescript';
import {readFileSync} from 'node:fs';
import {resolve, relative} from 'node:path';
import {pathToFileURL} from 'node:url';

export function usedOperations(program, root) {
  const checker = program.getTypeChecker();
  const client = resolve(root, 'src/api/index.ts');
  const used = new Set();
  for (const file of program.getSourceFiles()) {
    const name = relative(resolve(root, 'src'), file.fileName);
    if (name.startsWith('..') || file.isDeclarationFile || /\.(test|spec)\.[tj]sx?$/.test(name)) continue;
    function visit(node) {
      if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
        const prop = node.expression.name.text;
        const declaration = checker.getResolvedSignature(node)?.declaration;
        if (declaration && resolve(declaration.getSourceFile().fileName) === client) {
          const args = node.arguments;
          const route = prop === 'blob' ? args[0] : args[1];
          const method = prop === 'blob' ? 'get' : args[0] && ts.isStringLiteralLike(args[0]) && args[0].text;
          if ((prop === 'blob' || prop === 'call') && method && route && ts.isStringLiteralLike(route)) {
            used.add(method.toUpperCase() + ' ' + route.text);
          }
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(file);
  }
  return used;
}

export function report(spec, used, allow) {
  const rows = [];
  for (const [path, ops] of Object.entries(spec.paths)) {
    for (const [method, op] of Object.entries(ops)) {
      if (!op.operationId) continue;
      const key = method.toUpperCase() + ' ' + path;
      const reason = allow[key];
      const status = used.has(key) ? 'used' : typeof reason === 'string' && reason.trim() ? 'allowed: ' + reason : 'unused';
      rows.push({key, status});
    }
  }
  return rows;
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const root = process.cwd();
  const read = path => JSON.parse(readFileSync(resolve(root, path), 'utf8'));
  const config = ts.readConfigFile('tsconfig.json', ts.sys.readFile);
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, root);
  const program = ts.createProgram(parsed.fileNames, parsed.options);
  const allow = read('coverage-allowlist.json');
  const rows = report(read('../../../packages/contracts/openapi-v2.json'), usedOperations(program, root), allow);
  for (const {key, status} of rows) console.log(status + '  ' + key);
  const unknown = Object.keys(allow).filter(key => !rows.some(r => r.key === key));
  if (unknown.length) console.error('Unknown allowlist entries:', unknown.join(', '));
  const missing = rows.filter(r => r.status === 'unused').length;
  console.log(rows.length + ' operations, ' + missing + ' unused');
  process.exitCode = Number(unknown.length > 0 || (missing > 0 && !process.argv.slice(2).includes('--report')));
}
