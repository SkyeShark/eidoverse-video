"""Serve the local kit inspector without exposing the rest of the checkout. MIT."""
import argparse,http.server,functools
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class Handler(http.server.SimpleHTTPRequestHandler):
 def permitted(self):
  from urllib.parse import urlsplit,unquote
  path=unquote(urlsplit(self.path).path)
  if path=='/':
   query=urlsplit(self.path).query
   self.send_response(302);self.send_header('Location','/eidoverse/robotics/inspector/'+('?' + query if query else ''));self.end_headers();return False
  resolved=(ROOT/path.lstrip('/')).resolve()
  if not any(resolved.is_relative_to(p) for p in [ROOT/'eidoverse/robotics',ROOT/'eidoverse/assets/robotics']):self.send_error(404);return False
  return True
 def do_GET(self):
  if self.permitted():return super().do_GET()
 def do_HEAD(self):
  if self.permitted():return super().do_HEAD()
 def end_headers(self):self.send_header('Cache-Control','no-cache');super().end_headers()
 def log_message(self,*args):pass
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8989);args=parser.parse_args()
 server=http.server.ThreadingHTTPServer(('127.0.0.1',args.port),functools.partial(Handler,directory=str(ROOT)))
 print(f'Eidoverse robotics inspector: http://127.0.0.1:{server.server_port}/',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:server.server_close()
