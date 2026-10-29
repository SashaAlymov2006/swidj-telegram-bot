"""Create a reproducible resource plot/table from the bounded VPS load test."""
import argparse,collections,csv,json,statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args();root=args.directory
metrics=json.loads((root/'load5-metrics.json').read_text());result=json.loads((root/'load5-results.json').read_text());samples=metrics['samples'];cores=metrics['cores']
phases=list(dict.fromkeys(row['phase'] for row in samples));phase_stats=[]
for phase in phases:
    points=[row for row in samples if row['phase']==phase];requests=[row for row in result['requests'] if row['phase']==phase]
    times=sorted(row['seconds'] for row in requests)
    phase_stats.append({'phase':phase,'seconds':round(points[-1]['seconds']-points[0]['seconds'],2),
        'host_cpu_mean':statistics.mean(row.get('host_cpu_percent',0) for row in points),'host_cpu_max':max(row.get('host_cpu_percent',0) for row in points),
        'main_memory_max_gib':max(row['main_memory_bytes'] for row in points)/2**30,
        'video_memory_max_mib':max(row['video_memory_bytes'] for row in points)/2**20,
        'requests':len(requests),'status_counts':dict(collections.Counter(row['status'] for row in requests)),
        'median_seconds':statistics.median(times) if times else None,'max_seconds':max(times) if times else None})
stats={'duration_seconds':samples[-1]['seconds'],'cores':cores,'requests':len(result['requests']),
       'http_status_counts':dict(collections.Counter(row['status'] for row in result['requests'])),
       'host_cpu_max':max(row.get('host_cpu_percent',0) for row in samples),
       'main_cpu_max_one_core_percent':max(row.get('main_cpu_percent',0) for row in samples),
       'main_memory_peak_gib':max(row['main_memory_bytes'] for row in samples)/2**30,
       'video_memory_peak_mib':max(row['video_memory_bytes'] for row in samples)/2**20,
       'host_memory_available_min_gib':min(row['host_available_bytes'] for row in samples)/2**30,
       'safety_stop':any(row.get('safety_stop') for row in samples),'phases':phase_stats}
(root/'summary.json').write_text(json.dumps(stats,indent=2))
with (root/'resource_samples.csv').open('w',newline='') as stream:
    keys=sorted(set().union(*(row.keys() for row in samples)));writer=csv.DictWriter(stream,keys);writer.writeheader();writer.writerows(samples)

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
fig,axes=plt.subplots(2,1,figsize=(14,8),sharex=True,layout='constrained');x=[row['seconds'] for row in samples]
axes[0].plot(x,[row.get('host_cpu_percent',0) for row in samples],label='Весь VPS',color='#1c5d99',linewidth=1.8)
axes[0].plot(x,[row.get('main_cpu_percent',0)/cores for row in samples],label='Контейнер бота/API',color='#e2872d',linewidth=1.3)
axes[0].plot(x,[row.get('video_cpu_percent',0)/cores for row in samples],label='Видеосервис',color='#008b78',linewidth=1.3)
axes[0].set(ylabel='CPU, % всей мощности VPS',ylim=(0,102));axes[0].legend(loc='upper left',ncol=3)
axes[1].plot(x,[row['main_memory_bytes']/2**30 for row in samples],label='Бот/API',color='#e2872d')
axes[1].plot(x,[row['video_memory_bytes']/2**30 for row in samples],label='Видеосервис',color='#008b78')
axes[1].plot(x,[row['host_used_bytes']/2**30 for row in samples],label='Весь VPS (с учётом доступного кеша)',color='#1c5d99')
axes[1].set(ylabel='RAM, GiB',xlabel='Время от начала теста, секунды',ylim=(0,16));axes[1].legend(loc='upper left',ncol=3)
labels={'baseline':'Простой','setup_public_audio':'Подготовка','five_listeners':'5 плееров','five_searches':'5 поисков',
        'five_chat_download_workers_cold':'5 загрузчиков бота','five_studio_submissions':'5 запросов студии',
        'video_prepare_five':'Подготовка видео','five_video_renders':'5 видео в очереди','cooldown':'После теста'}
sessions=result.get('sessions',5)
if sessions!=5:
    labels={key.replace('five_', 'three_') if sessions==3 else key:value.replace('5 ',str(sessions)+' ') for key,value in labels.items()}
for i,row in enumerate(phase_stats):
    if row['phase'] not in labels:continue
    points=[s['seconds'] for s in samples if s['phase']==row['phase']];start,end=points[0],points[-1]
    for axis in axes:
        axis.axvspan(start,end,color='#dce8f0' if i%2 else '#edf4f8',alpha=.35,zorder=0)
        axis.axvline(start,color='#b2bec8',linewidth=.6)
    axes[0].text((start+end)/2,100,labels[row['phase']],rotation=75,ha='left',va='bottom',fontsize=8)
for axis in axes:axis.grid(alpha=.18)
fig.suptitle(f'SwiDJ: тестовых сессий — {sessions} · действующий VPS · 4 vCPU / 16 GB RAM\n{stats["duration_seconds"]:.1f} секунды; 45-секундное аудио и 2-секундные видео 1080p30',fontsize=13)
fig.savefig(root/'load-five-users.png',dpi=150)
print(json.dumps({k:v for k,v in stats.items() if k!='phases'},indent=2))
