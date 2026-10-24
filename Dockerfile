FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TMPDIR=/app/tmp
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
# Optional trusted CA bundle for intercepted enterprise/cloud build networks.
# TLS verification remains enabled; the bundle is not stored in the image.
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install --no-cache-dir -r requirements.txt
COPY requirements-youtube.txt ./
RUN pip install --no-cache-dir -r requirements-youtube.txt
COPY --from=denoland/deno:bin-2.9.8 /deno /usr/local/bin/deno
COPY requirements-miniapp.txt ./
RUN pip install --no-cache-dir -r requirements-miniapp.txt
RUN useradd --uid 10001 --create-home bot && mkdir -p /app/data /app/tmp /home/bot/.cache && chown -R bot:bot /app/data /app/tmp /home/bot/.cache
COPY --chmod=0444 bot.py access.py state_store.py audio_tools.py bass_labels.py miniapp_server.py dispatch.py recognition_flow.py subscriptions.py scratch.py media_store.py railway_start.py diagnostics.py search_quality.py studio_tools.py studio_ui.py audio_presentation.py operations.py versions.py library_ui.py lyrics_search.py effect_preview.py owner_panel.py uploaded_media.py ui_layout.py video_presentation.py track_card.py quick_studio.py catalog_links.py link_queue.py i18n_ui.py i18n_en.json ./
COPY --chmod=0555 miniapp/ ./miniapp/
USER bot
CMD ["python", "bot.py"]
