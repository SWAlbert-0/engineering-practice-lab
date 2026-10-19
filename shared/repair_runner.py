"""Trusted Docker Engine client. Only the worker receives the daemon socket."""
import http.client
import json
import os
import re
import socket
import struct
import time
from urllib.parse import quote
from shared.repair_fixtures import canonical

class RunnerError(RuntimeError):pass
class RunnerTimeout(RunnerError):pass
class DockerConnection(http.client.HTTPConnection):
    def __init__(self,path):super().__init__('localhost',timeout=5);self.path=path
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(self.timeout);self.sock.connect(self.path)

POLICY={'network':'none','read_only':True,'memory_mb':128,'cpus':0.5,'pids':32,'user':'65534:65534','tmpfs_mb':16,'wall_seconds':20,'mounts':[]}
def container_config(image,workspace,task,payload):
    return {'Image':image,'Cmd':['python','-I','-S','/opt/repair/repair_judge.py'],'User':POLICY['user'],
            'Env':['PYTHONUTF8=1','PYTHONDONTWRITEBYTECODE=1','LAB_REPAIR_PAYLOAD='+canonical(payload)],
            'Labels':{'repair.lab.workspace':workspace,'repair.lab.task':task},'NetworkDisabled':True,
            'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'Memory':128*1024*1024,'MemorySwap':128*1024*1024,
                          'NanoCpus':500000000,'PidsLimit':32,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges:true'],
                          'Tmpfs':{'/tmp':'rw,noexec,nosuid,size=16m,mode=1777'},'LogConfig':{'Type':'json-file','Config':{'max-size':'256k','max-file':'1'}},
                          'Binds':[],'AutoRemove':False,'RestartPolicy':{'Name':'no'}}}

def verify_container(info,image):
    host=info.get('HostConfig',{});config=info.get('Config',{})
    checks=[info.get('Image')==image,config.get('User')==POLICY['user'],host.get('NetworkMode')=='none',host.get('ReadonlyRootfs') is True,
            host.get('Memory')==134217728,host.get('MemorySwap')==134217728,host.get('NanoCpus')==500000000,host.get('PidsLimit')==32,
            'ALL' in host.get('CapDrop',[]),any(x.startswith('no-new-privileges') for x in host.get('SecurityOpt',[])),
            not host.get('Privileged'),not host.get('Binds'),all(m.get('Type')=='tmpfs' and m.get('Destination')=='/tmp' for m in info.get('Mounts',[])),set(host.get('Tmpfs',{}))=={'/tmp'}]
    env=config.get('Env',[])
    checks.append(not any(x.startswith(('LAB_LLM_','LAB_EMBED_','DOCKER_HOST=')) for x in env))
    if not all(checks):raise RunnerError('执行环境未满足固定隔离策略，已停止。')
    return dict(POLICY)

def decode_logs(raw):
    out=bytearray();pos=0
    while pos+8<=len(raw):
        header=raw[pos:pos+8];size=struct.unpack('>I',header[4:])[0]
        if header[0] not in (1,2) or header[1:4]!=b'\0\0\0' or size>len(raw)-pos-8:raise RunnerError('运行器日志协议无效。')
        out.extend(raw[pos+8:pos+8+size]);pos+=8+size
    if pos!=len(raw):raise RunnerError('运行器日志未完整返回。')
    return out.decode('utf-8')

class DockerRunner:
    def __init__(self,workspace,image=None,socket_path=None):
        self.workspace=workspace;self.tag=image or os.environ.get('LAB_REPAIR_IMAGE','engineering-practice-lab-repair:local');self.socket_path=socket_path or '/var/run/docker.sock';self.version='';self.image_id=None
    def request(self,method,path,body=None,*,raw=False,missing_ok=False):
        conn=DockerConnection(self.socket_path)
        try:
            encoded=canonical(body).encode() if body is not None else None
            conn.request(method,('/v'+self.version if self.version else '')+path,encoded,{'Content-Type':'application/json'})
            response=conn.getresponse();data=response.read(300000)
            if response.status==404 and missing_ok:return None
            if not 200<=response.status<300:raise RunnerError('Docker 请求失败（HTTP '+str(response.status)+'），请检查运行器和执行镜像。')
            if len(data)>=300000:raise RunnerError('执行产物超出大小限制。')
            return data if raw else json.loads(data) if data else {}
        except (OSError,http.client.HTTPException,ValueError):raise RunnerError('无法连接 Docker 执行器或读取执行结果。') from None
        finally:conn.close()
    def prepare(self):
        daemon=self.request('GET','/version');version=daemon.get('ApiVersion','')
        if not re.fullmatch(r'1\.[0-9]+',version):raise RunnerError('Docker API 版本无效。')
        self.version=version;image=self.request('GET','/images/'+quote(self.tag,safe='')+'/json')
        self.image_id=image['Id']
        if not re.fullmatch('sha256:[a-f0-9]{64}',self.image_id):raise RunnerError('执行镜像标识无效。')
        if image.get('Config',{}).get('Volumes'):raise RunnerError('执行镜像不允许声明数据卷。')
        return {'kind':'docker','image_id':self.image_id,'policy':POLICY,'engine_version':daemon.get('Version')}
    def reap(self,is_terminal):
        filters=quote(canonical({'label':['repair.lab.workspace='+self.workspace]}),safe='')
        for row in self.request('GET','/containers/json?all=1&filters='+filters):
            task=row.get('Labels',{}).get('repair.lab.task')
            if task and is_terminal(task):self.request('DELETE','/containers/'+row['Id']+'?force=1',missing_ok=True)
    def cleanup_task(self,task):
        filters=quote(canonical({'label':['repair.lab.workspace='+self.workspace,'repair.lab.task='+task]}),safe='')
        for row in self.request('GET','/containers/json?all=1&filters='+filters):self.request('DELETE','/containers/'+row['Id']+'?force=1',missing_ok=True)
    def run(self,key,source,task,stopped=lambda:False):
        if not self.image_id:self.prepare()
        cid=None;began=time.monotonic();evidence=None
        try:
            if stopped():raise InterruptedError('运行已取消。')
            result=self.request('POST','/containers/create',container_config(self.image_id,self.workspace,task,{'repository':key,'source':source}));cid=result['Id']
            info=self.request('GET','/containers/'+cid+'/json');evidence=verify_container(info,self.image_id)
            self.request('POST','/containers/'+cid+'/start')
            while True:
                if stopped():raise InterruptedError('运行已取消。')
                if time.monotonic()-began>POLICY['wall_seconds']:raise RunnerTimeout('单次测试超过 20 秒，执行环境已回收。')
                info=self.request('GET','/containers/'+cid+'/json');state=info['State']
                if not state['Running']:
                    if state.get('OOMKilled'):raise RunnerError('执行超过 128 MiB 内存限制。')
                    if state['ExitCode']!=0:raise RunnerError('测试进程异常退出，未形成可认可的结果。')
                    raw=self.request('GET','/containers/'+cid+'/logs?stdout=1&stderr=1',raw=True)
                    try:result=json.loads(decode_logs(raw))
                    except (ValueError,UnicodeError):raise RunnerError('测试结果格式无效。') from None
                    return {**result,'environment':{'kind':'docker','image_id':self.image_id,'policy':evidence,'container_id':cid}}
                time.sleep(.1)
        finally:
            if cid:self.request('DELETE','/containers/'+cid+'?force=1',missing_ok=True)
