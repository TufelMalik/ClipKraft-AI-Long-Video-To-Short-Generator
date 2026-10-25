"""SQLite transactions serialize revisions across API workers; JSON is never client-owned."""
import json
import os
import sqlite3
import time
from contextlib import contextmanager, closing
from pathlib import Path
from edit_project import EditError, uid, validate


def process_alive(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class Store:
    def __init__(self, root):
        # Outside /videos' StaticFiles root: project data and encrypted OAuth records are private.
        self.root = Path(root).resolve().parent / '.longform' / Path(root).name
        self.root.mkdir(parents=True, exist_ok=True)
        if os.name != 'nt':
            self.root.chmod(0o700)
        self.path = self.root / 'projects.sqlite3'
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, body TEXT NOT NULL,
                    PRIMARY KEY(kind,id));
                CREATE TABLE IF NOT EXISTS slots (name TEXT PRIMARY KEY, owner TEXT, expires REAL);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                db.execute('PRAGMA busy_timeout=30000')
                db.execute('PRAGMA secure_delete=ON')
                db.execute('BEGIN IMMEDIATE')
                yield db
        finally:
            db.close()
            if os.name != 'nt':
                self.path.chmod(0o600)

    def prune(self):
        now = time.time()
        limits = {'report': ('fetched_at', 30 * 86400), 'oauth_state': ('expires', 0),
                  'media_ticket': ('expires', 0), 'lease': ('expires', 0)}
        with self.db() as db:
            for kind, (field, age) in limits.items():
                for id, raw in db.execute('SELECT id,body FROM records WHERE kind=?', (kind,)).fetchall():
                    if json.loads(raw).get(field, 0) + age < now:
                        db.execute('DELETE FROM records WHERE kind=? AND id=?', (kind, id))


    def get(self, kind, id):
        with self.db() as db:
            row = db.execute('SELECT body FROM records WHERE kind=? AND id=?', (kind, id)).fetchone()
        if not row:
            raise EditError('not_found')
        return json.loads(row[0])

    def put(self, kind, id, body):
        with self.db() as db:
            self._put(db, kind, id, body)
        return body

    @staticmethod
    def _put(db, kind, id, body):
        db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)', (kind, id, json.dumps(body, ensure_ascii=False)))

    def all(self, kind):
        with self.db() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT body FROM records WHERE kind=?', (kind,))]

    def delete(self, kind, id):
        with self.db() as db:
            db.execute('DELETE FROM records WHERE kind=? AND id=?', (kind, id))

    def clear(self, kind):
        with self.db() as db:
            db.execute('DELETE FROM records WHERE kind=?', (kind,))

    def take(self, kind, id):
        with self.db() as db:
            row = db.execute('SELECT body FROM records WHERE kind=? AND id=?', (kind, id)).fetchone()
            if not row:
                raise EditError('invalid_oauth_state')
            db.execute('DELETE FROM records WHERE kind=? AND id=?', (kind, id))
            return json.loads(row[0])

    def mutate(self, id, revision, change):
        if type(revision) is not int:
            raise EditError('revision_conflict')
        with self.db() as db:
            row = db.execute("SELECT body FROM records WHERE kind='project' AND id=?", (id,)).fetchone()
            if not row:
                raise EditError('not_found')
            p = json.loads(row[0])
            if p['revision'] != revision:
                raise EditError('revision_conflict')
            updated = validate(change(json.loads(row[0])))
            updated['revision'] = revision + 1
            self._put(db, 'history', f'{id}:{revision}', p)
            self._put(db, 'project', id, updated)
        return updated

    @contextmanager
    def slot(self, name, seconds=1800):
        owner = f'{os.getpid()}:{uid()}'
        with self.db() as db:
            db.execute('DELETE FROM slots WHERE expires < ?', (time.time(),))
            for slot, existing in db.execute('SELECT name,owner FROM slots').fetchall():
                if ':' in existing and not process_alive(int(existing.split(':')[0])):
                    db.execute('DELETE FROM slots WHERE name=?', (slot,))
            try:
                db.execute('INSERT INTO slots VALUES (?,?,?)', (name, owner, time.time() + seconds))
            except sqlite3.IntegrityError:
                raise EditError('resource_busy')
        try:
            yield
        finally:
            with self.db() as db:
                db.execute('DELETE FROM slots WHERE name=? AND owner=?', (name, owner))


def lease_active(root, job_id, now=None):
    """Read-only cleanup hook. No database is created for existing shorts installs."""
    path = Path(root).resolve().parent / '.longform' / Path(root).name / 'projects.sqlite3'
    if not path.is_file():
        return False
    try:
        with closing(sqlite3.connect(path, timeout=1)) as db:
            row = db.execute("SELECT body FROM records WHERE kind='lease' AND id=?", (job_id,)).fetchone()
        return bool(row and json.loads(row[0])['expires'] > (time.time() if now is None else now))
    except (sqlite3.Error, ValueError, KeyError):
        return False
