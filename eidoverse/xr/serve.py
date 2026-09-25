#!/usr/bin/env python3
"""Serve Eidoverse WebXR pages to a headset on your LAN, and collect what the headset reports.

    python3 eidoverse/xr/serve.py                      # HTTPS :8892 on the LAN, HTTP 127.0.0.1:8894
    python3 eidoverse/xr/serve.py --home /work/<id>/vr/index.html --log work/<id>/vr/results.jsonl

- HTTPS on every interface (the headset browser only allows WebXR on a secure origin), plus plain HTTP on
  127.0.0.1 for desktop previews and headless stills (eidoverse/xr/shot.mjs).
- A self-signed certificate for this machine's LAN address is made with openssl the first time, and made
  again whenever the address changes or it is about to expire (work/.xr_cert/, gitignored). The headset
  asks you to accept it once per address and port (Advanced -> Proceed).
- Only these are served, from the repo root: /work/, /eidoverse/, and three.js + three-vrm from
  node_modules (run `python eido.py bootstrap` once), with an extension whitelist. Add more with --allow.
  Import maps point at /node_modules/three/build/three.webgpu.js etc., the renderer's own three version.
- POST /report appends the JSON body, stamped with the server time, to --log (one line per report). The
  kit (xr_kit.js) sends heartbeats, fps and errors there, so a session can be read back after the fact.
- No caching: a reload on the headset always gets the file you just saved.
"""
import argparse
import datetime
import http.server
import json
import os
import posixpath
import socket
import ssl
import subprocess
import sys
import threading
import urllib.parse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PREFIXES = ['/work/', '/eidoverse/', '/node_modules/three/', '/node_modules/@pixiv/']
EXTS = ('.html', '.js', '.mjs', '.json', '.css', '.wasm', '.bin', '.glb', '.gltf', '.vrm', '.vrma', '.png', '.jpg',
        '.jpeg', '.webp', '.ktx2', '.hdr', '.exr', '.m4a', '.mp3', '.ogg', '.wav', '.mp4', '.webm', '.txt')
TYPES = {'.js': 'text/javascript', '.mjs': 'text/javascript', '.wasm': 'application/wasm', '.m4a': 'audio/mp4',
         '.ogg': 'audio/ogg', '.bin': 'application/octet-stream', '.vrm': 'model/gltf-binary',
         '.vrma': 'model/gltf-binary', '.glb': 'model/gltf-binary', '.hdr': 'application/octet-stream'}
MAX_REPORT = 1 << 20


def lan_ip():
    """This machine's address on the LAN (a UDP 'connect' sends nothing)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('192.0.2.1', 9))
        return s.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        s.close()


def ensure_cert(ip, folder):
    """A self-signed certificate valid for ip, 127.0.0.1 and localhost; remade when the ip changes or it expires."""
    os.makedirs(folder, exist_ok=True)
    crt, key = os.path.join(folder, 'cert.pem'), os.path.join(folder, 'key.pem')
    if os.path.exists(crt) and os.path.exists(key):          # (-text and -checkend: OpenSSL and LibreSSL both)
        text = subprocess.run(['openssl', 'x509', '-in', crt, '-noout', '-text'], capture_output=True, text=True)
        fresh = subprocess.run(['openssl', 'x509', '-in', crt, '-noout', '-checkend', str(7 * 86400)],
                               capture_output=True).returncode == 0
        if fresh and f'IP Address:{ip}' in text.stdout:
            return crt, key
    print(f'making a certificate for {ip} in {folder}', flush=True)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '365', '-keyout', key,
                    '-out', crt, '-subj', '/CN=eidoverse-xr',
                    '-addext', f'subjectAltName=IP:{ip},IP:127.0.0.1,DNS:localhost'],
                   check=True, capture_output=True)
    return crt, key


def make_handler(allow, home, log_path, lock):
    class Handler(http.server.SimpleHTTPRequestHandler):
        extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map, **TYPES)

        def __init__(self, *a, **kw):
            super().__init__(*a, directory=ROOT, **kw)

        def log_message(self, fmt, *args):     # quiet: errors only
            if args and str(args[1])[:1] in '45':
                sys.stderr.write('%s %s\n' % (self.address_string(), fmt % args))

        def do_GET(self):
            path, _, query = self.path.partition('?')
            p = posixpath.normpath(urllib.parse.unquote(path))
            if p in ('/', '.'):
                self.send_response(302)
                self.send_header('Location', home + ('?' + query if query else ''))
                self.end_headers()
                return
            if '..' in p.split('/') or not any(p.startswith(x) for x in allow) or not p.lower().endswith(EXTS):
                self.send_error(404)
                return
            return super().do_GET()
        do_HEAD = do_GET

        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            super().end_headers()

        def do_POST(self):
            if self.path.split('?')[0] != '/report':
                self.send_error(404)
                return
            n = int(self.headers.get('Content-Length') or 0)
            if n > MAX_REPORT:
                self.send_error(413)
                return
            body = self.rfile.read(n)
            try:
                rec = json.loads(body or b'{}')
                if not isinstance(rec, dict):
                    rec = {'value': rec}
            except ValueError:
                rec = {'raw': body[:2000].decode('utf-8', 'replace')}
            rec.setdefault('at_server', datetime.datetime.now().isoformat(timespec='milliseconds'))
            rec.setdefault('from', self.client_address[0])
            with lock, open(log_path, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(rec) + '\n')
            self.send_response(204)
            self.end_headers()
    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8892, help='HTTPS port on every interface (the headset)')
    ap.add_argument('--http-port', type=int, default=8894, help='plain HTTP on 127.0.0.1 (desktop, stills)')
    ap.add_argument('--home', default='/eidoverse/xr/example.html', help='where / redirects (query kept)')
    ap.add_argument('--log', default='work/xr_reports.jsonl', help='where POST /report lines go (repo-relative)')
    ap.add_argument('--allow', action='append', default=[], metavar='PREFIX', help='serve another path prefix')
    ap.add_argument('--cert-dir', default='work/.xr_cert')
    a = ap.parse_args()

    allow = PREFIXES + [x if x.endswith('/') else x + '/' for x in a.allow]
    log_path = os.path.join(ROOT, a.log)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    if not os.path.isdir(os.path.join(ROOT, 'node_modules', 'three')):
        print('note: node_modules/three is missing, so pages cannot import three.js: run `python eido.py bootstrap`')
    ip = lan_ip()
    crt, key = ensure_cert(ip, os.path.join(ROOT, a.cert_dir))
    handler = make_handler(allow, a.home, log_path, threading.Lock())

    https = http.server.ThreadingHTTPServer(('0.0.0.0', a.port), handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    https.socket = ctx.wrap_socket(https.socket, server_side=True)
    plain = http.server.ThreadingHTTPServer(('127.0.0.1', a.http_port), handler)
    threading.Thread(target=plain.serve_forever, daemon=True).start()
    print(f'headset:  https://{ip}:{a.port}/   (accept the certificate once: Advanced -> Proceed)')
    print(f'desktop:  http://127.0.0.1:{a.http_port}/')
    print(f'reports:  {os.path.relpath(log_path, ROOT)}', flush=True)
    try:
        https.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
