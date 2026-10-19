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
requirements=load('05-requirements');literature=load('06-literature');video=load('04-video-understanding')
from shared.model_client import configured

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def do_GET(self):
        if self.path=='/healthz':return self.reply(200,{'status':'ok','projects':6})
        if self.path=='/api/capabilities':return self.reply(200,{'llm':configured()})
        return super().do_GET()
    def do_POST(self):
        try:
            origin=self.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=self.headers.get('Host'):
                return self.reply(403,{'error':'仅接受同源请求'})
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=250000:raise ValueError('请求大小无效')
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
            elif self.path=='/api/requirements':result=requirements.analyze(data.get('text'),data.get('mode','offline'))
            elif self.path=='/api/requirements/compare':result=requirements.compare(data.get('before'),data.get('after'))
            elif self.path=='/api/literature':result=literature.run(data.get('topic'),data.get('ids'),data.get('mode','offline'))
            elif self.path=='/api/video':result=video.run(data.get('question'),data.get('frames'),data.get('mode','offline'),data.get('duration',0))
            else:return self.reply(404,{'error':'不存在的 API'})
            self.reply(200,result)
        except (ValueError,TypeError,KeyError) as e:self.reply(400,{'error':str(e)})
        except Exception:
            import traceback;traceback.print_exc();self.reply(500,{'error':'执行失败，请查看服务端日志'})
    def reply(self,status,data):
        content=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--host',default='127.0.0.1',help='Bind address; containers use 0.0.0.0')
    p.add_argument('--port',type=int,default=8765)
    a=p.parse_args(argv)
    if not 1 <= a.port <= 65535:p.error('port must be between 1 and 65535')
    with ThreadingHTTPServer((a.host,a.port),Handler) as httpd:
        print(f'Engineering Topic Lab listening on {a.host}:{a.port}',flush=True)
        try:httpd.serve_forever()
        except KeyboardInterrupt:pass

if __name__=='__main__':
    main()
