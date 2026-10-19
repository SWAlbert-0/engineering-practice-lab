"""Local demo server. No arbitrary repository/code execution endpoint."""
import argparse, functools, importlib.util, json, math
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote
ROOT=Path(__file__).resolve().parent

def load(folder):
    path=ROOT/'demos'/folder/'engine.py'
    spec=importlib.util.spec_from_file_location(folder,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
repair=load('01-repair-agent');rag=load('02-process-rag');mlops=load('03-mlops')
requirements=load('05-requirements');literature=load('06-literature');video=load('04-video-understanding')
from shared.model_client import configured
from shared.process_workspace import get_workspace, WorkspaceError
from shared.requirements_workspace import get_requirements_workspace

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def end_headers(self):
        # Revalidate UI files after upgrades; API/binary replies already use no-store.
        # A cached legacy script and the new HTML have incompatible dependencies.
        if getattr(self,'_serving_static',False):
            self.send_header('Cache-Control','no-cache')
        super().end_headers()
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/healthz':return self.reply(200,{'status':'ok','projects':6})
        if path=='/api/capabilities':return self.reply(200,{'llm':configured()})
        if path.startswith('/api/requirements-workspace/'):
            try:
                w=get_requirements_workspace();parts=path.removeprefix('/api/requirements-workspace/').strip('/').split('/')
                q=parse_qs(urlsplit(self.path).query);version=q.get('version',[None])[0]
                if parts==['workspace']:result=w.state()
                elif len(parts)==2 and parts[0]=='documents':result=w.document(parts[1],version)
                elif len(parts)==3 and parts[0]=='documents' and parts[2]=='changes':result=w.changes(parts[1],int(q.get('before',['1'])[0]),int(q.get('after',['1'])[0]))
                elif len(parts)==2 and parts[0]=='sets':result=w.suite(parts[1],version)
                elif len(parts)==3 and parts[0] in ('sets','releases') and parts[2]=='export':return self.binary(*w.export(parts[1],q.get('format',['json'])[0],version,parts[0]=='releases'))
                else:raise WorkspaceError('接口不存在。',404)
                return self.reply(200,result)
            except WorkspaceError as error:return self.reply(error.status,{'error':str(error)})
            except (ValueError,TypeError):return self.reply(400,{'error':'请求参数无效。'})
            except Exception:
                import traceback;traceback.print_exc();return self.reply(500,{'error':'读取需求工作区失败，请查看服务端日志。'})
        if path.startswith('/api/process/'):
            try:
                w=get_workspace();parts=path.removeprefix('/api/process/').strip('/').split('/')
                query=parse_qs(urlsplit(self.path).query);version=query.get('version',[None])[0]
                if parts==['workspace']:result=w.state()
                elif len(parts)==2 and parts[0]=='documents':result=w.document(parts[1],version)
                elif len(parts)==3 and parts[0]=='documents' and parts[2]=='file':return self.binary(*w.raw_document(parts[1],version))
                elif len(parts)==2 and parts[0]=='evaluations':result=w.evaluation(parts[1])
                elif len(parts)==2 and parts[0]=='searches':result=w.retrieval(parts[1])
                elif len(parts)>=2 and parts[0]=='drafts':
                    version=int(version) if version else None
                    if len(parts)==3 and parts[2]=='export':return self.binary(*w.export(parts[1],query.get('format',['json'])[0],version))
                    if len(parts)!=2:raise WorkspaceError('接口不存在。',404)
                    result=w.draft(parts[1],version)
                else:raise WorkspaceError('接口不存在。',404)
                return self.reply(200,result)
            except WorkspaceError as error:return self.reply(error.status,{'error':str(error)})
            except (ValueError,TypeError):return self.reply(400,{'error':'请求参数无效。'})
            except Exception:
                import traceback;traceback.print_exc();return self.reply(500,{'error':'读取工作区失败，请检查服务端数据与日志。'})
        # Only public resources are served; the database and local secrets never are.
        requested=unquote(path);parts=Path(requested.lstrip('/')).parts
        allowed={'demos','shared','report','docs','screenshots'}
        if any(p.startswith('.') for p in parts) or (parts and parts[0] not in allowed and requested not in ('/','/index.html','/README.md')):
            return self.reply(404,{'error':'资源不存在。'})
        resolved=(ROOT/requested.lstrip('/')).resolve()
        import os
        data=Path(os.environ.get('LAB_DATA_DIR',str(ROOT/'data'))).resolve()
        if not resolved.is_relative_to(ROOT) or resolved.is_relative_to(data):return self.reply(404,{'error':'资源不存在。'})
        self._serving_static=True
        try:return super().do_HEAD() if self.command=='HEAD' else super().do_GET()
        finally:self._serving_static=False
    def do_HEAD(self):
        # HEAD follows the same resource restrictions; no private-file metadata leaks.
        return self.do_GET()
    def binary(self,content,mime,name):
        self.send_response(200);self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(content)));self.send_header('Content-Disposition','attachment; filename="'+name+'"')
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers()
        if self.command!='HEAD':self.wfile.write(content)
    def do_POST(self):
        try:
            origin=self.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=self.headers.get('Host'):
                return self.reply(403,{'error':'仅接受同源请求'})
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=(12*1024*1024 if self.path.startswith(('/api/process/','/api/requirements-workspace/')) else 250000):raise ValueError('请求大小无效')
            if 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('需要 JSON')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError('需要 JSON 对象')
            if self.path.startswith('/api/requirements-workspace/'):
                parts=urlsplit(self.path).path.removeprefix('/api/requirements-workspace/').strip('/').split('/');w=get_requirements_workspace();status=200
                if parts==['documents']:result=w.import_document(data);status=201
                elif parts==['imports']:result=w.import_bundle(data);status=201
                elif len(parts)==3 and parts[0]=='documents' and parts[2]=='revisions':result=w.revise(parts[1],data)
                elif len(parts)==3 and parts[0]=='documents' and parts[2]=='analyses':result=w.analyze(parts[1],data);status=202
                elif len(parts)==3 and parts[0]=='sets':
                    action=parts[2]
                    if action=='draft':result=w.save_draft(parts[1],data)
                    elif action=='discard-draft':result=w.discard_draft(parts[1],data)
                    elif action=='commit':result=w.commit(parts[1],data)
                    elif action=='reviews':result=w.review(parts[1],data)
                    elif action=='publish':result=w.publish(parts[1],data)
                    else:raise WorkspaceError('接口不存在。',404)
                elif len(parts)==3 and parts[0]=='jobs':result=w.job_action(parts[1],parts[2])
                else:raise WorkspaceError('接口不存在。',404)
                return self.reply(status,result)
            if self.path.startswith('/api/process/'):
                parts=urlsplit(self.path).path.removeprefix('/api/process/').strip('/').split('/');w=get_workspace()
                status=200
                if parts==['documents']:result=w.import_document(data);status=202
                elif parts==['search']:result=w.search(data)
                elif parts==['drafts']:result=w.generate(data);status=202
                elif parts==['evaluate']:result=w.evaluate(data);status=202
                elif parts==['rebuild']:result=w.enqueue('rebuild',{'strategy':data.get('strategy','lsa')});status=202
                elif len(parts)==3 and parts[0]=='documents' and parts[2]=='delete':result=w.delete(parts[1])
                elif len(parts)==3 and parts[0]=='jobs':result=w.job_action(parts[1],parts[2])
                elif len(parts)==3 and parts[0]=='drafts' and parts[2]=='save':result=w.save_draft(parts[1],data)
                elif len(parts)==3 and parts[0]=='drafts' and parts[2]=='review':result=w.review(parts[1],data)
                else:raise WorkspaceError('接口不存在。',404)
                return self.reply(status,result)
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
        except WorkspaceError as e:self.reply(e.status,{'error':str(e)})
        except (ValueError,TypeError,KeyError) as e:self.reply(400,{'error':str(e)})
        except Exception:
            import traceback;traceback.print_exc();self.reply(500,{'error':'执行失败，请查看服务端日志'})
    def reply(self,status,data):
        content=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.end_headers();
        if self.command!='HEAD':self.wfile.write(content)

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--host',default='127.0.0.1',help='Bind address; containers use 0.0.0.0')
    p.add_argument('--port',type=int,default=8765)
    a=p.parse_args(argv)
    if not 1 <= a.port <= 65535:p.error('port must be between 1 and 65535')
    workspace=get_workspace();requirements_workspace=get_requirements_workspace()
    with ThreadingHTTPServer((a.host,a.port),Handler) as httpd:
        print(f'Engineering Topic Lab listening on {a.host}:{a.port}',flush=True)
        try:httpd.serve_forever()
        except KeyboardInterrupt:pass
        finally:workspace.close();requirements_workspace.close()

if __name__=='__main__':
    main()
