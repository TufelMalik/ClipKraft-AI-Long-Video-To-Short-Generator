// One request per job at a time, with bounded retries during a server outage.
// Completed sessions are reconciled once so saved clip URLs cannot live forever.
export function createJobPoller({ getSessions, pollJob, onUpdate, onError,
  now = Date.now, schedule = setTimeout, cancel = clearTimeout, interval = 2000,
  reconcileCompleted = true }) {
  const jobs = new Map();
  let stopped = false;
  let timer;

  const tick = () => {
    if (stopped) return;
    const sessions = getSessions().filter((s) => s.jobId &&
      (s.status === 'processing' || (reconcileCompleted &&
        ['completed', 'complete'].includes(s.status))));
    const liveKeys = new Set(sessions.map((s) => `${s.id}:${s.jobId}`));
    for (const key of jobs.keys()) if (!liveKeys.has(key)) jobs.delete(key);
    for (const session of sessions) {
      const key = `${session.id}:${session.jobId}`;
      const job = jobs.get(key) || { busy: false, done: false, failures: 0, next: 0 };
      jobs.set(key, job);
      if (job.busy || job.done || job.next > now()) continue;
      job.busy = true;
      Promise.resolve().then(() => pollJob(session.jobId)).then((data) => {
        if (stopped || jobs.get(key) !== job) return;
        job.failures = 0;
        job.done = data.notFound || ['not_found', 'completed', 'failed', 'cancelled'].includes(data.status);
        onUpdate(session, data);
      }).catch((error) => {
        if (stopped || jobs.get(key) !== job) return;
        job.failures += 1;
        job.next = now() + Math.min(30000, interval * 2 ** Math.min(job.failures, 4));
        if (job.failures === 1) onError?.(session, error);
      }).finally(() => {
        job.busy = false;
      });
    }
    timer = schedule(tick, interval);
  };
  tick();
  return () => {
    stopped = true;
    cancel(timer);
  };
}
