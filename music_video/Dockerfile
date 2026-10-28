FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TMPDIR=/tmp
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY music_video/requirements-server.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home swidjvideo && mkdir /data && chown swidjvideo:swidjvideo /data
COPY --chmod=0444 music_video/__init__.py music_video/model.py music_video/render.py music_video/server.py ./music_video/
COPY --chmod=0555 music_video/web/ ./music_video/web/
COPY --chmod=0444 miniapp/visualizer-bridge.js ./miniapp/
RUN chmod 0555 /app/music_video /app/music_video/web /app/miniapp
USER swidjvideo
EXPOSE 8792
CMD ["python","-m","music_video.server","--root","/data"]
