#!/usr/bin/env python3
"""Swarm Impact Receipt. Local-only Python 3.10+ application."""
import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from domain import CATALOG, IDENTITIES, SCENARIOS, contract_inputs, summary, receipt_markdown, require
from storage import Store, Conflict

ROOT = Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    store = None
    token = None

    def log_message(self, *args):
        pass

    def send(self, code, value, mime='application/json; charset=utf-8', filename=None):
        raw = json.dumps(value, allow_nan=False).encode() if mime.startswith('application/json') else value
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(raw)

    def trusted(self):
        port = self.server.server_port
        return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

    def do_GET(self):
        if not self.trusted():
            return self.send(403, {'error': 'invalid_host'})
        url = urlsplit(self.path)
        path = url.path
        try:
            files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path in files:
                name, mime = files[path]
                return self.send(200, (ROOT / 'web' / name).read_bytes(), mime)
            if path == '/api/state':
                version, state = self.store.read()
                return self.send(200, dict(version=version, state=state, summary=summary(state), token=self.token, catalog=CATALOG, identities=IDENTITIES, scenarios=SCENARIOS, defaults=contract_inputs()))
            if path == '/api/events':
                return self.send(200, [{k: v for k, v in e.items() if k not in ('state', 'data')} for e in self.store.events()])
            if path == '/api/replay':
                return self.send(200, self.store.replay())
            if path == '/api/export':
                version, state = self.store.read()
                return self.send(200, dict(schema_version=1, synthetic=True, version=version, state=state, summary=summary(state), replay=self.store.replay(), events=self.store.events()), filename='swarm-impact-receipts.json')
            if path == '/api/events.jsonl':
                raw = '\n'.join(json.dumps(e, allow_nan=False) for e in self.store.events()) + '\n'
                return self.send(200, raw.encode(), 'application/x-ndjson', 'swarm-impact-events.jsonl')
            if path == '/api/receipt.md':
                _, state = self.store.read()
                rid = parse_qs(url.query).get('id', [''])[0]
                for c in state['contracts']:
                    for m in c['measurements']:
                        if m['id'] == rid:
                            return self.send(200, receipt_markdown(c, m).encode(), 'text/markdown; charset=utf-8', rid + '.md')
                return self.send(404, {'error': 'receipt_not_found'})
            if path == '/api/evaluation':
                file = ROOT / 'fixtures' / 'evaluation-report.json'
                return self.send(200, json.loads(file.read_text()) if file.exists() else {'status': 'Run python3 evaluate.py'})
            self.send(404, {'error': 'not_found'})
        except ValueError as error:
            self.send(409, {'error': str(error)})

    def do_POST(self):
        if not self.trusted() or not secrets.compare_digest(self.headers.get('X-Receipt-Token', ''), self.token):
            return self.send(403, {'error': 'invalid_session'})
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            return self.send(403, {'error': 'invalid_origin'})
        if self.path != '/api/command':
            return self.send(404, {'error': 'not_found'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            require(0 < size <= 32768, 'request_size_limit')
            require(self.headers.get_content_type() == 'application/json', 'json_required')
            req = json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('non_finite_json')))
            return self.send(200, self.store.change(req))
        except Conflict as error:
            return self.send(409, {'error': str(error)})
        except (ValueError, KeyError, TypeError) as error:
            return self.send(400, {'error': str(error)})
        except Exception:
            return self.send(500, {'error': 'internal_error'})


def make_server(db_path, port=8766):
    class AppHandler(Handler):
        store = Store(db_path)
        token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(('127.0.0.1', port), AppHandler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--db', default=str(ROOT / 'data' / 'receipts.sqlite'))
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    if args.replay:
        print(json.dumps(Store(args.db).replay(), indent=2))
        return
    server = make_server(args.db, args.port)
    print(f'Swarm Impact Receipt: http://127.0.0.1:{server.server_port}', flush=True)
    print('Synthetic local demo. Data saved in SQLite. Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
