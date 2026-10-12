"""Transactional snapshots, deterministic command replay and immutable evidence."""
import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from domain import canonical, digest, require, mutation, latest
from demo import seed_state


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts = self.path.parent / (self.path.stem + '-artifacts')
        self.artifacts.mkdir(exist_ok=True)
        with self.connect() as db:
            require(db.execute('PRAGMA user_version').fetchone()[0] in (0, 1), 'unsupported_database_schema')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, key TEXT UNIQUE NOT NULL, request_hash TEXT NOT NULL, body TEXT NOT NULL, hash TEXT NOT NULL)')
            db.execute('PRAGMA user_version=1')
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM events LIMIT 1').fetchone():
                self.append(db, 'seed-v1', 'seed', {}, 'system', seed_state())

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def evidence_put(self, state):
        for c in state['contracts']:
            for m in c['measurements']:
                raw = canonical(m['evidence']).encode()
                path = self.artifacts / (m['evidence_hash'] + '.json')
                if path.exists():
                    require(path.read_bytes() == raw, 'corrupt_evidence_artifact')
                    continue
                fd, temp = tempfile.mkstemp(dir=self.artifacts)
                try:
                    with os.fdopen(fd, 'wb') as f:
                        f.write(raw)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temp, path)
                finally:
                    if os.path.exists(temp):
                        os.unlink(temp)

    def check_artifacts(self, state):
        for c in state['contracts']:
            for m in c['measurements']:
                path = self.artifacts / (m['evidence_hash'] + '.json')
                require(path.is_file(), 'missing_evidence_artifact')
                require(path.read_bytes() == canonical(m['evidence']).encode() and digest(m['evidence']) == m['evidence_hash'], 'corrupt_evidence_artifact')

    def append(self, db, key, command, data, actor, state):
        row = db.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        self.evidence_put(state)
        body = dict(schema_version=1, recorded_at=datetime.now(timezone.utc).isoformat(), demo_at=state['clock'], command=command, data=data, actor=actor, state=state, previous_hash=row[0] if row else None)
        db.execute('INSERT INTO events(key,request_hash,body,hash) VALUES(?,?,?,?)', (key, digest(dict(command=command, data=data, actor=actor)), canonical(body), digest(body)))

    def read(self):
        with self.connect() as db:
            seq, raw, expected = db.execute('SELECT seq,body,hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        body = json.loads(raw)
        require(digest(body) == expected, 'corrupt_event_snapshot')
        self.check_artifacts(body['state'])
        return seq, body['state']

    def change(self, request):
        require(isinstance(request, dict) and set(request) == {'command', 'data', 'actor', 'key', 'expected_version'}, 'invalid_command_envelope')
        require(type(request['expected_version']) is int, 'invalid_expected_version')
        for k in ('command', 'actor', 'key'):
            require(isinstance(request[k], str) and 0 < len(request[k]) <= 160, 'invalid_' + k)
        require(isinstance(request['data'], dict), 'invalid_data')
        fingerprint = digest({k: request[k] for k in ('command', 'data', 'actor')})
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            duplicate = db.execute('SELECT seq,request_hash FROM events WHERE key=?', (request['key'],)).fetchone()
            if duplicate:
                if duplicate[1] != fingerprint:
                    raise Conflict('idempotency_key_reused')
                return dict(replayed=True, event_version=duplicate[0])
            seq, raw, expected = db.execute('SELECT seq,body,hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
            if seq != request['expected_version']:
                raise Conflict('stale_version_refresh_and_retry')
            body = json.loads(raw)
            require(digest(body) == expected, 'corrupt_event_snapshot')
            self.check_artifacts(body['state'])
            state = mutation(body['state'], request['command'], request['data'], request['actor'])
            self.append(db, request['key'], request['command'], request['data'], request['actor'], state)
        return dict(saved=True, event_version=seq + 1)

    def events(self):
        with self.connect() as db:
            rows = db.execute('SELECT seq,body,hash FROM events ORDER BY seq').fetchall()
        return [dict(seq=seq, hash=h, **json.loads(raw)) for seq, raw, h in rows]

    def replay(self):
        previous = None
        reconstructed = None
        events = self.events()
        for e in events:
            body = {k: v for k, v in e.items() if k not in ('seq', 'hash')}
            require(body['schema_version'] == 1, 'unknown_schema')
            require(body['previous_hash'] == previous and digest(body) == e['hash'], 'audit_hash_mismatch')
            reconstructed = seed_state() if e['command'] == 'seed' else mutation(reconstructed, e['command'], e['data'], e['actor'])
            require(canonical(reconstructed) == canonical(e['state']), 'command_replay_mismatch')
            previous = e['hash']
        self.check_artifacts(reconstructed)
        return dict(verified=True, events=len(events), state_hash=digest(reconstructed), method='Deterministic command replay + hash and artifact verification', tamper_proof=False)
