"""Local demo server. No arbitrary repository/code execution endpoint."""
import argparse, functools, importlib.util, json, math
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parent

def load(folder):
    path=ROOT/'demos'/folder/'engine.py'
    spec=importlib.util.spec_from_file_location(folder,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
repair=load('01-repair-agent');rag=load('02-process-rag');mlops=load('03-mlops')

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def do_POST(self):
        try:
            origin=self.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=self.headers.get('Host'):
                return self.reply(403,{'error':'仅接受同源请求'})
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=50000:raise ValueError('请求大小无效')
            if 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('需要 JSON')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError('需要 JSON 对象')
            if self.path=='/api/repair':result=repair.run(data.get('case','boundary'),data.get('candidate','correct'))
            elif self.path=='/api/rag':
                q=data.get('query','');material=data.get('material','全部')
                if not isinstance(q,str) or not 1<=len(q.strip())<=600:raise ValueError('请输入 1–600 字的问题')
                result=rag.search(q,material,data.get('mode','hybrid'))
            elif self.path=='/api/mlops':
                noise=float(data.get('noise',0.4));shift=float(data.get('shift',0));labels=data.get('labels',True)
                if not math.isfinite(noise+shift) or not 0<=noise<=1 or not 0<=shift<=3:raise ValueError('参数超出范围')
                if not isinstance(labels,bool):raise ValueError('labels 必须为布尔值')
                result=mlops.run(noise,shift,labels)
            else:return self.reply(404,{'error':'不存在的 API'})
            self.reply(200,result)
        except (ValueError,TypeError,KeyError) as e:self.reply(400,{'error':str(e)})
        except Exception:
            import traceback;traceback.print_exc();self.reply(500,{'error':'执行失败，请查看服务端日志'})
    def reply(self,status,data):
        content=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    print(f'Engineering Topic Lab: http://127.0.0.1:{a.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
