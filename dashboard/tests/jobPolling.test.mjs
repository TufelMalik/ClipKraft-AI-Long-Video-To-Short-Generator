import test from 'node:test';
import assert from 'node:assert/strict';
import { createJobPoller } from '../src/lib/jobPolling.js';

const flush = () => new Promise((resolve) => setImmediate(resolve));
function harness(pollJob, sessions = [{ id: 's', jobId: 'j', status: 'processing' }], options = {}) {
  let time = 0;
  let next = 1;
  const timers = new Map();
  const updates = [], errors = [];
  const stop = createJobPoller({
    getSessions: () => sessions, pollJob,
    onUpdate: (...args) => updates.push(args), onError: (...args) => errors.push(args),
    now: () => time,
    schedule: (fn, delay) => { const id = next++; timers.set(id, { fn, at: time + delay }); return id; },
    cancel: (id) => timers.delete(id), ...options,
  });
  return { sessions, updates, errors, stop, async advance(ms) {
    time += ms;
    for (const [id, timer] of [...timers]) {
      if (timer.at <= time) { timers.delete(id); timer.fn(); }
    }
    await flush();
  } };
}

test('requests never overlap when status is slow', async () => {
  let calls = 0, finish;
  const h = harness(() => { calls++; return new Promise((r) => { finish = r; }); });
  await flush();
  await h.advance(2000);
  await h.advance(2000);
  assert.equal(calls, 1);
  finish({ status: 'processing' });
  await flush();
  await h.advance(2000);
  assert.equal(calls, 2);
  h.stop();
});

test('outages back off and report one warning until recovery', async () => {
  let calls = 0, online = false;
  const h = harness(async () => { calls++; if (!online) throw new Error('offline'); return { status: 'processing' }; });
  await flush();
  await h.advance(2000);
  assert.equal(calls, 1);
  await h.advance(2000);
  assert.equal(calls, 2);
  await h.advance(6000);
  assert.equal(calls, 2);
  online = true;
  await h.advance(2000);
  assert.equal(h.updates.length, 1);
  assert.equal(h.errors.length, 1);
  await h.advance(2000);
  assert.equal(calls, 4);
  h.stop();
});

test('reconciles a restored complete session once, including missing jobs', async () => {
  for (const result of [{ status: 'completed', result: { clips: [{ video_url: '/new.mp4' }] } },
    { status: 'not_found', notFound: true }]) {
    let calls = 0;
    const h = harness(async () => { calls++; return result; }, [{ id: 's', jobId: 'j', status: 'complete' }]);
    await flush();
    await h.advance(2000);
    await h.advance(30000);
    assert.equal(calls, 1);
    assert.deepEqual(h.updates[0][1], result);
    h.stop();
  }
});

test('one stalled job does not block another session', async () => {
  const h = harness((id) => id === 'slow' ? new Promise(() => {}) : Promise.resolve({ status: 'completed' }),
    [{ id: 'a', jobId: 'slow', status: 'processing' }, { id: 'b', jobId: 'fast', status: 'processing' }]);
  await flush();
  assert.equal(h.updates[0][0].jobId, 'fast');
  h.stop();
});

test('ignores responses after cleanup and after a job is replaced', async () => {
  let finish;
  const h = harness(() => new Promise((r) => { finish = r; }));
  await flush();
  h.stop();
  finish({ status: 'completed' });
  await flush();
  assert.equal(h.updates.length, 0);
});

test('new jobs are discovered without recreating the polling timer', async () => {
  const h = harness(async () => ({ status: 'completed' }));
  await flush();
  h.sessions.push({ id: 's2', jobId: 'j2', status: 'processing' });
  await h.advance(2000);
  assert.deepEqual(h.updates.map(([s]) => s.jobId), ['j', 'j2']);
  h.stop();
});

test('cloud completed projects remain under the existing durable restore flow', async () => {
  const calls = [];
  const h = harness(async (id) => { calls.push(id); return { status: 'processing' }; },
    [{ id: 'a', jobId: 'archived', status: 'complete' },
      { id: 'b', jobId: 'running', status: 'processing' }], { reconcileCompleted: false });
  await flush();
  assert.deepEqual(calls, ['running']);
  h.stop();
});
