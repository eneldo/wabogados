// Isolated server-module contract tests: no real cookies, users or network.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const directory = path.dirname(fileURLToPath(import.meta.url));

function load(file, dependencies, fetch) {
  const box = {
    exports: {},
    require: key => {
      if (!(key in dependencies)) throw new Error(`Unexpected import: ${key}`);
      return dependencies[key];
    },
    process: { env: { API_INTERNAL_URL: 'http://backend:8000' } },
    URL, FormData, fetch,
  };
  const source = fs.readFileSync(path.join(directory, '..', file), 'utf8');
  // Preserve native Error subclassing, as in the actual Next.js build.
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(output, box);
  return box.exports;
}

(async () => {
  const landing = load('lib/landing.ts', {}, undefined);
  for (const scenario of ['absent', 'unauthorized', 'unavailable', 'network', 'administrator']) {
    const calls = [];
    const upstream = async url => {
      calls.push(url);
      assert.ok(url.startsWith('http://backend:8000/'));
      if (scenario === 'network') throw new Error('Connection unavailable');
      if (scenario === 'unauthorized') return Response.json({}, { status: 401 });
      if (scenario === 'unavailable') return Response.json({ error: { message: 'Temporarily unavailable' } }, { status: 503 });
      return Response.json(url.endsWith('/auth/me')
        ? { id: 'test', roles: ['cliente', 'administrador'], permissions: ['cases:read_all'] }
        : { unread_messages: 0, unread_notifications: 0 });
    };
    const session = { readAccessToken: async () => scenario === 'absent' ? undefined : 'dummy-test-value' };
    const api = load('lib/api.ts', { './session': session }, upstream);
    const profile = load('lib/profile.ts', { '@/lib/api': api, '@/lib/session': session, '@/lib/landing': landing }, upstream);
    const guard = load('lib/session-guard.ts', {
      'next/navigation': { redirect: () => { throw new Error('Unexpected redirect'); } },
      '@/lib/api': api, '@/lib/profile': profile,
    }, upstream);
    const result = await guard.requireSession();
    const expected = ['absent', 'unauthorized'].includes(scenario)
      ? 'unauthenticated' : scenario === 'administrator' ? 'ok' : 'unavailable';
    assert.equal(result.kind, expected);
    if (scenario === 'absent') assert.equal(calls.length, 0);
    if (scenario === 'administrator') assert.equal(result.profile.isClient, false);
    console.log(`PASS isolated session guard: ${scenario} -> ${result.kind}`);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
