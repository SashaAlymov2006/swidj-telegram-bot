"""VPS host wrapper: sample cgroup CPU/RAM without docker-stats polling overhead."""
import fcntl,json,os,subprocess,threading,time
from pathlib import Path

ROOT=Path('/opt/swidj/deployment');samples=[];done=threading.Event()
lock=(ROOT/'load5.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
def container(name):
    info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];pid=info['State']['Pid']
    relative=next(line.split('::',1)[1] for line in Path(f'/proc/{pid}/cgroup').read_text().splitlines() if '::' in line)
    return info,Path('/sys/fs/cgroup')/relative.lstrip('/'),Path(f'/proc/{pid}/root/tmp')
main,main_cgroup,tmp=container('swidj-vps-bot-1');video,video_cgroup,_=container('swidj-visual-music-video-1')
(tmp/'swidj-load5-stop').unlink(missing_ok=True)
(tmp/'swidj-load5-phase.json').write_text(json.dumps({'phase':'startup','time':time.time()}))
started=time.monotonic();previous={}
def read_cpu(path):return int(dict(line.split() for line in (path/'cpu.stat').read_text().splitlines())['usage_usec'])
def memory(path):
    stats={key:int(value) for key,value in (line.split() for line in (path/'memory.stat').read_text().splitlines())}
    return max(0,int((path/'memory.current').read_text())-stats.get('inactive_file',0))
def monitor():
    while not done.is_set():
        now=time.monotonic();row={'seconds':round(now-started,3)}
        try:row['phase']=json.loads((tmp/'swidj-load5-phase.json').read_text())['phase']
        except (OSError,ValueError):row['phase']='startup'
        mem={key:int(value.split()[0])*1024 for key,value in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
        row['host_available_bytes']=mem['MemAvailable'];row['host_used_bytes']=mem['MemTotal']-mem['MemAvailable']
        for name,path in [('main',main_cgroup),('video',video_cgroup)]:
            cpu=read_cpu(path);row[name+'_memory_bytes']=memory(path)
            if name in previous:
                at,old=previous[name];row[name+'_cpu_percent']=(cpu-old)/(now-at)/10000
            previous[name]=(now,cpu)
        stat=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]));total=sum(stat);idle=stat[3]+stat[4]
        if 'host' in previous:
            old_total,old_idle=previous['host'];row['host_cpu_percent']=100*(1-(idle-old_idle)/max(1,total-old_total))
        previous['host']=(total,idle)
        if mem['MemAvailable']<1024**3 or row['main_memory_bytes']>11*1024**3:
            (tmp/'swidj-load5-stop').touch();row['safety_stop']=True
        samples.append(row);done.wait(.5)

thread=threading.Thread(target=monitor);thread.start()
try:
    with (ROOT/'load5-run.log').open('w') as log:
        subprocess.run(['docker','exec','-e','PYTHONPATH=/app','-e','OMP_NUM_THREADS=2','-e','MKL_NUM_THREADS=2',
                        'swidj-vps-bot-1','python','/tmp/load_five_users.py'],stdout=log,stderr=subprocess.STDOUT,timeout=720,check=True)
finally:
    done.set();thread.join()
    (ROOT/'load5-metrics.json').write_text(json.dumps({'cores':os.cpu_count(),'main_cpu_limit':main['HostConfig']['NanoCpus']/1e9,
       'main_memory_limit':main['HostConfig']['Memory'],'main_started_before':main['State']['StartedAt'],'samples':samples},indent=2))
    subprocess.run(['docker','cp','swidj-vps-bot-1:/tmp/swidj-load5-results.json',str(ROOT/'load5-results.json')],check=True)
    print(json.dumps({'samples':len(samples),'metrics_saved':True}))
