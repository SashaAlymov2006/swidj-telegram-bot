"""Mini App limits; independent of Telegram chat upload restrictions."""
MEDIA_BYTES = 256*1024**2
MEDIA_SECONDS = 2*60*60
STUDIO_OUTPUT_BYTES = 512*1024**2
TEMP_CACHE_BYTES = 1024*1024**2
LIBRARY_USER_BYTES = 512*1024**2
LIBRARY_TOTAL_BYTES = 2*1024**3

# Link downloads have no product size/duration cap by default (0 = disabled).
# Studio processing and permanent-library quotas remain independent.
import os
import shutil
LINK_MAX_BYTES=max(0,int(os.getenv('MINIAPP_LINK_MAX_BYTES','0')))
LINK_MAX_SECONDS=max(0,int(os.getenv('MINIAPP_LINK_MAX_SECONDS','0')))
DISK_RESERVE_BYTES=512*1024**2
LINK_QUALITIES=(0,144,240,360,480,720,1080)
def link_budget(directory):
    available=(shutil.disk_usage(directory).free-DISK_RESERVE_BYTES)//3
    if available<=0:raise OSError('Not enough disk space')
    return min(available,LINK_MAX_BYTES) if LINK_MAX_BYTES else available
