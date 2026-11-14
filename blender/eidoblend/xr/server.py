#!/usr/bin/env python3
"""eidoblend.xr.server: the kit's server (eidoverse/xr/serve.py) for the Blender edition's pages. Plain Python, no bpy.

The kit's server carries over as it is: HTTPS on every interface for the headset (a self-signed certificate for this
machine's LAN address, made with openssl and remade when the address changes or it nears expiry), plain HTTP on
127.0.0.1 for the desktop and for stills, POST /report appended to a JSONL log, no caching, a whitelist of folders and
file types. This module runs THAT server's own handler, imported from eidoverse/xr/serve.py (not copied), and adds what
the Blender edition needs:

  - /blender/ is served as well (the page template and the kit check live there), plus any --allow prefix;
  - /node_modules/ can come from another folder (--node-modules): a git worktree has no node_modules of its own until
    `python eido.py bootstrap` runs in it, so point it at a checkout that has them;
  - start(): the same server in a thread, for tests and scripts (an ephemeral port, HTTPS optional, stop()).

    python blender/eidoblend/xr/server.py --home /work/<id>/vr/index.html --log work/<id>/vr/results.jsonl
    python blender/eidoblend/xr/server.py --node-modules <a checkout>/node_modules

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.xr import server
    srv = server.start(log='work/<id>/vr/results.jsonl')        # srv.url  http://127.0.0.1:<port>
    ...
    srv.stop()
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import posixpath
import ssl
import sys
import threading
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
KIT_SERVE = os.path.join(REPO, 'eidoverse', 'xr', 'serve.py')
EXTRA_PREFIXES = ['/blender/']


def kit():
    """eidoverse/xr/serve.py as a module (lan_ip, ensure_cert, make_handler, PREFIXES, EXTS, TYPES, MAX_REPORT)."""
    mod = sys.modules.get('eido_xr_serve')
    if mod is None:
        spec = importlib.util.spec_from_file_location('eido_xr_serve', KIT_SERVE)
        mod = importlib.util.module_from_spec(spec)
        keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True     # (no __pycache__ left in the kit's folder)
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.dont_write_bytecode = keep
        sys.modules['eido_xr_serve'] = mod
    return mod


def find_node_modules(explicit=None):
    """The node_modules folder pages import three.js from: `explicit`, EIDO_NODE_MODULES, this repo's own, or None."""
    for c in (explicit, os.environ.get('EIDO_NODE_MODULES'), os.path.join(REPO, 'node_modules')):
        if c and os.path.isdir(os.path.join(c, 'three')):
            return os.path.abspath(c)
    return None


def make_handler(allow=None, home='/eidoverse/xr/example.html', log_path=None, node_modules=None, lock=None):
    """The kit's handler (make_handler of eidoverse/xr/serve.py) with /node_modules/ read from `node_modules` when
    given. allow: extra path prefixes on top of the kit's (/work/, /eidoverse/, three + three-vrm) and /blender/."""
    k = kit()
    prefixes = list(k.PREFIXES) + EXTRA_PREFIXES + [x if x.endswith('/') else x + '/' for x in (allow or [])]
    log_path = os.path.abspath(log_path or os.path.join(REPO, 'work', 'xr_reports.jsonl'))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    base = k.make_handler(prefixes, home, log_path, lock or threading.Lock())
    nm = os.path.abspath(node_modules) if node_modules else None

    class Handler(base):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)

        def translate_path(self, path):
            p = posixpath.normpath(urllib.parse.unquote(path.split('?', 1)[0].split('#', 1)[0]))
            if nm and p.startswith('/node_modules/'):
                return os.path.join(nm, *[x for x in p[len('/node_modules/'):].split('/') if x not in ('', '.', '..')])
            return super().translate_path(path)

    Handler.prefixes = prefixes
    Handler.log_path = log_path
    return Handler


class Running:
    """A server started by start(): url (HTTP on 127.0.0.1), https_url (or None), log_path, stop()."""

    def __init__(self, servers, url, https_url, log_path):
        self._servers, self.url, self.https_url, self.log_path = servers, url, https_url, log_path

    def stop(self):
        for s in self._servers:
            s.shutdown()
            s.server_close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()


def start(http_port=0, https_port=None, home='/eidoverse/xr/example.html', log=None, allow=None, node_modules=None,
          cert_dir=None, bind_https='0.0.0.0'):
    """Serve in background threads. http_port 0 picks a free port. https_port (e.g. 8892, or 0) adds the headset's
    HTTPS server with the kit's certificate (made in cert_dir, default <repo>/work/.xr_cert). Returns Running."""
    import http.server
    k = kit()
    nm = find_node_modules(node_modules)
    handler = make_handler(allow, home, log, nm)
    servers, threads = [], []
    plain = http.server.ThreadingHTTPServer(('127.0.0.1', int(http_port)), handler)
    servers.append(plain)
    url = f'http://127.0.0.1:{plain.server_address[1]}'
    https_url = None
    if https_port is not None:
        ip = k.lan_ip()
        crt, key = k.ensure_cert(ip, os.path.abspath(cert_dir or os.path.join(REPO, 'work', '.xr_cert')))
        sec = http.server.ThreadingHTTPServer((bind_https, int(https_port)), handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(crt, key)
        sec.socket = ctx.wrap_socket(sec.socket, server_side=True)
        servers.append(sec)
        https_url = f'https://{ip}:{sec.server_address[1]}'
    for s in servers:
        t = threading.Thread(target=s.serve_forever, daemon=True)
        t.start()
        threads.append(t)
    return Running(servers, url, https_url, handler.log_path)


def main(argv=None):
    import http.server
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8892, help='HTTPS port on every interface (the headset)')
    ap.add_argument('--http-port', type=int, default=8894, help='plain HTTP on 127.0.0.1 (desktop, stills)')
    ap.add_argument('--home', default='/eidoverse/xr/example.html', help='where / redirects (query kept)')
    ap.add_argument('--log', default='work/xr_reports.jsonl', help='where POST /report lines go (repo-relative)')
    ap.add_argument('--allow', action='append', default=[], metavar='PREFIX', help='serve another path prefix')
    ap.add_argument('--cert-dir', default='work/.xr_cert')
    ap.add_argument('--node-modules', default=None, help="a node_modules folder with three (default: EIDO_NODE_MODULES, "
                                                          "then this repo's own)")
    a = ap.parse_args(argv)
    k = kit()
    nm = find_node_modules(a.node_modules)
    if nm is None:
        print('note: no node_modules with three found, so pages cannot import three.js: run `python eido.py bootstrap` '
              'here or pass --node-modules <a checkout>/node_modules')
    log_path = a.log if os.path.isabs(a.log) else os.path.join(REPO, a.log)
    handler = make_handler(a.allow, a.home, log_path, nm)
    ip = k.lan_ip()
    cert_dir = a.cert_dir if os.path.isabs(a.cert_dir) else os.path.join(REPO, a.cert_dir)
    crt, key = k.ensure_cert(ip, cert_dir)
    https = http.server.ThreadingHTTPServer(('0.0.0.0', a.port), handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    https.socket = ctx.wrap_socket(https.socket, server_side=True)
    plain = http.server.ThreadingHTTPServer(('127.0.0.1', a.http_port), handler)
    threading.Thread(target=plain.serve_forever, daemon=True).start()
    print(f'headset:  https://{ip}:{a.port}/   (accept the certificate once: Advanced -> Proceed)')
    print(f'desktop:  http://127.0.0.1:{a.http_port}/')
    print(f'reports:  {os.path.relpath(handler.log_path, REPO)}')
    print(f'three:    {nm or "MISSING"}', flush=True)
    try:
        https.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
