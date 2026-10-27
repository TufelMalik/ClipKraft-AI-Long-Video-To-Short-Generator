import test from 'node:test';
import assert from 'node:assert/strict';
import { readEditResponse } from './editApiResponse.js';

test('reads successful editor JSON and empty no-content responses', async () => {
  assert.deepEqual(await readEditResponse(new Response('{"revision":2}')), { revision: 2 });
  assert.equal(await readEditResponse(new Response(null, { status: 204 })), null);
});

test('preserves actionable FastAPI errors', async () => {
  await assert.rejects(readEditResponse(new Response('{"detail":"source_changed"}', { status: 400 })), /source_changed/);
});

test('plain-text server failure never becomes a JSON SyntaxError', async () => {
  await assert.rejects(readEditResponse(new Response('Internal Server Error', { status: 500 })), err =>
    !(err instanceof SyntaxError) && /HTTP 500/.test(err.message));
});

test('HTML proxy errors and invalid success bodies get readable messages', async () => {
  await assert.rejects(readEditResponse(new Response('<html>Bad gateway</html>', { status: 502 })), /HTTP 502/);
  await assert.rejects(readEditResponse(new Response('<html>App shell</html>')), /unexpected response/);
});
