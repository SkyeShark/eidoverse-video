"""tests/xr/test_xr_serve.py: the kit's Python tools carry over: eidoverse/xr/serve.py (through eidoblend.xr.server) and
eidoverse/xr/quest.py. System Python, no Blender, no GPU:

    python blender/tests/xr/test_xr_serve.py

serve.py's own handler, run by eidoblend.xr.server.start():
  - lan_ip(); ensure_cert() makes a self-signed certificate for the LAN address (openssl), and keeps it next time
  - HTTPS answers with that certificate (the headset's server); plain HTTP on 127.0.0.1 (desktop, stills)
  - '/' redirects to --home with the query kept; only the whitelisted folders and file types are served ('..' and
    other folders 404), .glb / .hdr / .js with their types, no caching
  - POST /report appends one stamped JSON line to the log; bodies over 1 MB are refused (413); non-JSON is kept raw
  - /node_modules/ from another folder (a worktree has none); /blender/ served (the page template, the kit check)
quest.py: its command line (every subcommand's --help). Its adb commands need adb and a headset: not here.
"""
import json
import os
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
OUT = os.path.join(HERE, 'out', 'serve')
os.makedirs(OUT, exist_ok=True)
MAIN_NODE_MODULES = os.path.abspath(os.path.join(WORKTREE, '..', 'eidoverse-video-prealpha-0.01', 'node_modules'))

from eidoblend.xr import server  # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def get(url, method='GET', data=None, ctx=None, follow=True):
    req = urllib.request.Request(url, data=data, method=method)
    opener = urllib.request.build_opener(*([] if follow else [NoRedirect()]),
                                         urllib.request.HTTPSHandler(context=ctx) if ctx else urllib.request.HTTPSHandler())
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, {k.title(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.title(): v for k, v in e.headers.items()}, e.read()


k = server.kit()
ip = k.lan_ip()
check('lan_ip(): an IPv4 address', ip.count('.') == 3, ip)
cert_dir = os.path.join(OUT, 'cert')
shutil.rmtree(cert_dir, ignore_errors=True)
has_openssl = shutil.which('openssl') is not None
if has_openssl:
    crt, key = k.ensure_cert(ip, cert_dir)
    m1 = os.path.getmtime(crt)
    crt2, _ = k.ensure_cert(ip, cert_dir)
    text = subprocess.run(['openssl', 'x509', '-in', crt, '-noout', '-text'], capture_output=True, text=True).stdout
    check('ensure_cert: a certificate for the LAN address, 127.0.0.1 and localhost', f'IP Address:{ip}' in text
          and 'IP Address:127.0.0.1' in text and 'DNS:localhost' in text)
    check('ensure_cert: kept on the next call (same address, not near expiry)', os.path.getmtime(crt2) == m1)
else:
    check('openssl on PATH (the kit makes its certificate with it)', False, 'openssl not found')

log = os.path.join(OUT, 'reports.jsonl')
if os.path.exists(log):
    os.remove(log)
srv = server.start(http_port=0, https_port=0 if has_openssl else None, home='/eidoverse/xr/example.html', log=log,
                   node_modules=MAIN_NODE_MODULES, cert_dir=cert_dir)
try:
    u = srv.url
    st, h, _ = get(u + '/?t=4&view=table', follow=False)
    check("'/' redirects to --home, the query kept", st == 302 and h.get('Location') == '/eidoverse/xr/example.html?t=4&view=table',
          (st, h.get('Location')))
    st, h, body = get(u + '/eidoverse/xr/xr_kit.js')
    check('the kit is served, as JavaScript, never cached', st == 200 and h.get('Content-Type', '').startswith('text/javascript')
          and h.get('Cache-Control') == 'no-store' and b'WorldRig' in body, (st, h.get('Content-Type'), h.get('Cache-Control')))
    st, h, body = get(u + '/node_modules/three/build/three.webgpu.js')
    check('/node_modules/three from another checkout (--node-modules)', st == 200 and len(body) > 1_000_000, (st, len(body)))
    st, _, _ = get(u + '/blender/eidoblend/xr/page/xr_page.html')
    check('/blender/ is served (the page template)', st == 200, st)
    glb = os.path.join(HERE, 'out', 'city', 'vr', 'scene.glb')
    if os.path.exists(glb):
        st, h, body = get(u + '/blender/tests/xr/out/city/vr/scene.glb')
        check('a GLB is served as model/gltf-binary', st == 200 and h.get('Content-Type') == 'model/gltf-binary'
              and body[:4] == b'glTF', (st, h.get('Content-Type')))
    for bad in ('/blender/../AGENTS.md', '/docs/TOOLS.md', '/eidoverse/xr/serve.py', '/blender/eidoblend/xr/server.py'):
        st, _, _ = get(u + bad)
        check(f'refused: {bad} (outside the folders, or not a served type)', st == 404, st)
    st, _, _ = get(u + '/report', 'POST', json.dumps({'test': 'serve_check', 'phase': 'hb', 'frames': 3}).encode())
    st2, _, _ = get(u + '/report', 'POST', b'not json')
    st3, _, _ = get(u + '/report', 'POST', b'x' * ((1 << 20) + 10))
    st4, _, _ = get(u + '/elsewhere', 'POST', b'{}')
    lines = [json.loads(x) for x in open(log, encoding='utf-8')] if os.path.exists(log) else []
    check('POST /report: one stamped line per report (204)', st == 204 and any(r.get('test') == 'serve_check'
          and 'at_server' in r and r.get('from') == '127.0.0.1' for r in lines), lines[:1])
    check('POST /report: non-JSON kept raw', st2 == 204 and any(r.get('raw') == 'not json' for r in lines))
    check('POST /report: over 1 MB refused (413); other POSTs 404', st3 == 413 and st4 == 404, (st3, st4))
    if srv.https_url:
        ctx = ssl.create_default_context(cafile=crt)
        ctx.check_hostname = False
        st, _, body = get(srv.https_url.replace(ip, '127.0.0.1') + '/eidoverse/xr/example.html', ctx=ctx)
        check('HTTPS with the kit certificate (the headset URL)', st == 200 and b'xr_kit.js' in body, (srv.https_url, st))
finally:
    srv.stop()

# the command lines themselves: eidoverse/xr/serve.py unchanged (it serves the repo it lives in; this worktree has no
# node_modules, so it says so), and eidoblend/xr/server.py with --node-modules and --allow
import socket       # noqa: E402
import time         # noqa: E402

# make_handler(allow=...): another folder joins the kit's (a trailing slash added), still under the type whitelist
# (the repo has no folder outside the served ones holding a served type, so the whitelist is what a request shows)
h2 = server.make_handler(allow=['/voicebox'], log_path=os.path.join(OUT, 'allow_reports.jsonl'))
with server.start(http_port=0, node_modules=MAIN_NODE_MODULES, allow=['/voicebox'],
                  log=os.path.join(OUT, 'allow_reports.jsonl')) as s2:
    st_type, _, _ = get(s2.url + '/voicebox/engine.py')
check("allow=['/voicebox']: the folder joins the kit's prefixes and /blender/; its .py files stay unserved",
      '/voicebox/' in h2.prefixes and '/blender/' in h2.prefixes and set(server.kit().PREFIXES) <= set(h2.prefixes)
      and st_type == 404, (h2.prefixes, st_type))
check('find_node_modules: an explicit folder, else EIDO_NODE_MODULES, else none in a worktree without one',
      server.find_node_modules(MAIN_NODE_MODULES) == os.path.abspath(MAIN_NODE_MODULES)
      and (server.find_node_modules(None) is None or os.path.isdir(os.path.join(WORKTREE, 'node_modules', 'three'))
           or os.environ.get('EIDO_NODE_MODULES')), server.find_node_modules(None))


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


for label, script, extra in (
        ('eidoverse/xr/serve.py (the kit, unchanged)', os.path.join(WORKTREE, 'eidoverse', 'xr', 'serve.py'), []),
        ('eidoverse/xr/serve.py --allow /blender/', os.path.join(WORKTREE, 'eidoverse', 'xr', 'serve.py'),
         ['--allow', '/blender/']),
        ('eidoblend/xr/server.py', os.path.join(WORKTREE, 'blender', 'eidoblend', 'xr', 'server.py'),
         ['--node-modules', MAIN_NODE_MODULES])):
    hp, sp = free_port(), free_port()
    cli_log = os.path.join(OUT, 'cli_reports.jsonl')
    p = subprocess.Popen([sys.executable, '-u', script, '--port', str(sp), '--http-port', str(hp), '--log', cli_log,
                          '--cert-dir', cert_dir, '--home', '/eidoverse/xr/example.html'] + extra,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, t0 = [], time.time()
    while time.time() - t0 < 20:
        line = p.stdout.readline()
        if not line:
            break
        out.append(line.rstrip())
        if line.startswith('reports:') or line.startswith('three:'):
            if 'three:' in line or 'server.py' not in script:
                break
    try:
        st, _, body = get(f'http://127.0.0.1:{hp}/eidoverse/xr/xr_kit.js')
        st3, _, _ = get(f'http://127.0.0.1:{hp}/node_modules/three/build/three.webgpu.js')
        st5, _, _ = get(f'http://127.0.0.1:{hp}/report', 'POST', b'{"test": "cli"}')
        check(f'{label}: runs from its command line (HTTPS :{sp}, HTTP :{hp}), serves the kit, takes reports',
              st == 200 and st5 == 204 and any(x.startswith('headset:') for x in out), out[:4])
        st4, _, _ = get(f'http://127.0.0.1:{hp}/blender/eidoblend/xr/page/xr_page.html')
        if 'eidoblend' in script:
            check(f'{label}: three from --node-modules, /blender/ served', st3 == 200 and st4 == 200, (st3, st4))
        elif '--allow' in extra:
            check(f'{label}: --allow adds a folder (the Blender page template now served)', st4 == 200, st4)
        else:
            check(f'{label}: says three is missing here and 404s it; /blender/ is not its folder',
                  st3 == 404 and st4 == 404 and any('bootstrap' in x for x in out), (st3, st4, out[:1]))
    finally:
        p.terminate()
        p.wait(10)

# quest.py: the command line (adb and a headset are not on this machine)
quest = os.path.join(WORKTREE, 'eidoverse', 'xr', 'quest.py')
for sub in ([], ['status'], ['wireless'], ['open'], ['awake'], ['pull']):
    r = subprocess.run([sys.executable, quest] + sub + ['--help'], capture_output=True, text=True)
    check(f"quest.py {' '.join(sub) or '(top)'} --help", r.returncode == 0 and 'usage' in r.stdout.lower(), r.returncode)
r = subprocess.run([sys.executable, quest, 'pull', '--kind', 'photo', '--n', '2', '--out', 'x', '--sheet', '--help'],
                   capture_output=True, text=True)
check('quest.py pull takes --kind / --n / --out / --sheet', r.returncode == 0)
print(f"[note] adb on PATH: {shutil.which('adb') or 'no'} (quest.py's commands themselves need adb and a headset)")
n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f'[check] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
sys.exit(1 if n_fail else 0)
