"""Short API requests around long studio renders; safe owner-scoped polling/cancellation."""
import asyncio
from dataclasses import dataclass,field
import secrets
import time

@dataclass
class RenderJob:
 uid:int
 source:object
 directory:object
 settings:dict
 cleanup:object
 token:str=field(default_factory=lambda:secrets.token_hex(12))
 state:str='queued'
 error:str=None
 file:object=None
 task:object=None
 created:float=field(default_factory=time.monotonic)

class RenderJobs:
 def __init__(self,exports,slots,renderer):self.exports,self.slots,self.renderer=exports,slots,renderer;self.jobs={}
 def start(self,uid,source,directory,settings,cleanup):
  for key,job in list(self.jobs.items()):
   if job.task.done() and time.monotonic()-job.created>1800:self.jobs.pop(key)
  while len(self.jobs)>=32:
   completed=next((key for key,job in self.jobs.items() if job.task.done()),None)
   if completed is None:raise ValueError('Studio busy')
   self.jobs.pop(completed)
  if any(not job.task.done() for job in self.jobs.values()):raise ValueError('Studio busy')
  job=RenderJob(uid,source,directory,dict(settings),cleanup);self.jobs[job.token]=job;job.task=asyncio.create_task(self.work(job))
  def finished(task):
   if task.cancelled():
    job.state='cancelled'
    if job.cleanup:job.cleanup();job.cleanup=None
  job.task.add_done_callback(finished)
  return job
 def get(self,uid,token):
  job=self.jobs.get(token)
  return job if job and job.uid==uid else None
 def cancel(self,uid,token):
  job=self.get(uid,token)
  if job and not job.task.done():job.task.cancel()
 def payload(self,job,origin):
  value={'job':job.token,'status':job.state,'error':job.error}
  if job.file:value['file']={'url':origin.rstrip('/')+'/studio-file/'+job.file['ticket'],'filename':job.file['filename'],'expires_in':3600}
  return value
 async def work(self,job):
  try:
   async with self.slots:
    job.state='processing';target=await self.renderer(job.source,job.directory,job.settings)
    from miniapp_studio import probe
    duration=await probe(target)
    token,item=self.exports.retain(job.uid,target,job.settings.get('title','SwiDJ mix'),ttl=max(3600,duration+600))
    job.file={'ticket':token,'filename':item['filename']};job.state='ready'
  except asyncio.CancelledError:job.state='cancelled'
  except OverflowError:job.state,job.error='failed','mediaTooLarge'
  except asyncio.TimeoutError:job.state,job.error='failed','studioTimeout'
  except Exception:job.state,job.error='failed','studioInvalid'
  finally:job.cleanup();job.cleanup=None
 async def close(self):
  tasks=[job.task for job in self.jobs.values() if not job.task.done()]
  for task in tasks:task.cancel()
  if tasks:await asyncio.gather(*tasks,return_exceptions=True)
