"""Convert real browser DJ captures through the production FFmpeg render path."""
import asyncio,json,tempfile
from pathlib import Path
from miniapp_studio import render,probe

async def main():
    for source in sorted(Path('/in').glob('dj-record-*')):
        if source.suffix not in ('.wav','.mp4','.webm'):continue
        before=await probe(source)
        with tempfile.TemporaryDirectory() as folder:
            target=await render(source,folder,{'format':'mp3'})
            after=await probe(target)
            assert abs(after-before)<.2 and target.stat().st_size>1000
            print(json.dumps({'capture':source.name,'input_seconds':round(before,3),'mp3_seconds':round(after,3),'mp3_bytes':target.stat().st_size}),flush=True)

asyncio.run(main())
