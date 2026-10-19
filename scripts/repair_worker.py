"""Dedicated trusted runner. Never expose this process or its Docker socket as an API."""
import argparse
import os
from pathlib import Path
import signal
import sys
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shared.repair_workspace import RepairWorkspace,FINAL
from shared.repair_runner import DockerRunner,RunnerError


def main():
    p=argparse.ArgumentParser();p.add_argument('--healthcheck',action='store_true');args=p.parse_args()
    # Start with only SETUID/SETGID, then use the application's data identity.
    # Socket group comes from the mounted socket; no host-specific GID setup.
    if os.geteuid()==0:
        socket_gid=Path('/var/run/docker.sock').stat().st_gid
        os.setgroups(sorted({10001,socket_gid}));os.setgid(10001);os.setuid(10001)
    os.umask(0o002)
    workspace=RepairWorkspace(os.environ.get('LAB_DATA_DIR','/data'),start_worker=False,mode='docker')
    if args.healthcheck:
        ok=workspace.capabilities()['ready'];workspace.close();return 0 if ok else 1
    runner=DockerRunner(workspace.workspace_id);finish=threading.Event();info={'ready':False,'message':'正在检查执行镜像与 Docker 连接。'};lock=threading.Lock()
    def beat():
        while not finish.is_set():
            with lock:status=dict(info)
            workspace.heartbeat_worker(status);finish.wait(2)
    heartbeat=threading.Thread(target=beat,daemon=True);heartbeat.start()
    def stop(*_):workspace.stop.set();finish.set()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        while not finish.is_set():
            try:
                prepared=runner.prepare()
                with lock:info.update(prepared,ready=True,message='独立 Docker 运行器已连接。')
                workspace.recover()
                def terminal(tid):
                    with workspace.connect() as c:
                        row=c.execute('SELECT status FROM tasks WHERE id=?',(tid,)).fetchone();return not row or row[0] in FINAL
                runner.reap(terminal)
                if not workspace.process_one(runner):finish.wait(.5)
            except RunnerError as error:
                with lock:info.update(ready=False,message=str(error))
                print('Repair runner unavailable: '+str(error),flush=True);finish.wait(2)
    finally:
        finish.set();heartbeat.join(3)
        workspace.heartbeat_worker({'ready':False,'message':'独立运行器已停止。'});workspace.close()
    return 0

if __name__=='__main__':raise SystemExit(main())
