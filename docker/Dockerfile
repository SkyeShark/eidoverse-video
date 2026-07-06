# Eidoverse render sandbox — Deno + WebGPU + Mesa + the full audio/asset
# toolchain. One Dockerfile, four flavors:
#
#   docker build -f docker/Dockerfile --build-arg AGENT=none     -t eidoverse:render docker
#   docker build -f docker/Dockerfile --build-arg AGENT=claude   -t eidoverse:claude docker
#   docker build -f docker/Dockerfile --build-arg AGENT=codex    -t eidoverse:codex docker
#   docker build -f docker/Dockerfile --build-arg AGENT=opencode -t eidoverse:opencode docker
#
# Build context = the docker/ dir (small, so BuildKit never walks the repo).
# The repo itself is NOT baked in — eido.py mounts it at /workspace at
# runtime, so engine changes never require a rebuild.
#
# Base is ubuntu:rolling so the Kisak PPA can install a recent Mesa — the
# stock LTS Mesa is too old for the WebGPU TSL post-processing passes.
# GPU path on Windows/WSL2: wgpu → Mesa D3D12 Gallium → /dev/dxg → host
# NVIDIA driver. On native Linux: Vulkan via mesa-vulkan-drivers.

FROM ubuntu:rolling
ARG AGENT=none
ENV DEBIAN_FRONTEND=noninteractive

# Node.js 20 (agent CLIs + puppeteer)
RUN apt-get update && apt-get install -y curl ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g npm@latest

# Non-root user early so chown works later
RUN useradd -m -s /bin/bash node

# Deno — runs the render engine (`deno run --allow-all --unstable-webgpu
# --node-modules-dir=auto eidoverse/render_scene.mjs <scene.json>`).
# `unzip` is required by the Deno installer.
RUN apt-get update && apt-get install -y --no-install-recommends unzip xz-utils && rm -rf /var/lib/apt/lists/*
# PINNED: Deno bundles wgpu/naga (the WebGPU shader translator); Deno 2.9.x
# silently corrupts the TSL post-effects path on this stack (renders become
# banded gradient garbage while every audit still passes). Bump only after
# checking a rendered FRAME, not just a successful render exit.
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh -s -- -y v2.8.1

# Static ffmpeg with nvenc support (BtbN GPL build — apt's ffmpeg sometimes
# lacks h264_nvenc depending on packaging).
# PINNED to a dated autobuild: "latest" tracks the newest nvenc SDK, which
# can demand a newer NVIDIA driver than the host has (e.g. API 13.1 needs
# driver 610+) and then every encode fails with "Driver does not support
# the required nvenc API version". Bump the pin deliberately, after
# checking your driver.
RUN curl -fsSL https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-03-31-13-11/ffmpeg-N-123777-g53537f6cf5-linux64-gpl.tar.xz \
        -o /tmp/ffmpeg.tar.xz && \
    tar -xJf /tmp/ffmpeg.tar.xz -C /tmp && \
    install -m 0755 /tmp/ffmpeg-N-123777-g53537f6cf5-linux64-gpl/bin/ffmpeg  /usr/local/bin/ffmpeg && \
    install -m 0755 /tmp/ffmpeg-N-123777-g53537f6cf5-linux64-gpl/bin/ffprobe /usr/local/bin/ffprobe && \
    rm -rf /tmp/ffmpeg.tar.xz /tmp/ffmpeg-N-123777-g53537f6cf5-linux64-gpl

# Custom display fonts (OFL-licensed; used by text_3d.js / canvas UI —
# see AGENTS.md font rules)
COPY fonts/*.ttf /usr/share/fonts/truetype/custom/
RUN chmod 644 /usr/share/fonts/truetype/custom/*.ttf

# System fonts + fontconfig + FluidSynth + GL/EGL + the shared-library set
# headless Chrome (fetch_model.py preview scraping) needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    fontconfig \
    libegl1 \
    libgles2 \
    libgl1 \
    libglx0 \
    libglvnd0 \
    mesa-vulkan-drivers \
    mesa-utils \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-noto-mono \
    fonts-noto-core \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-noto-extra \
    fluidsynth \
    fluid-soundfont-gm \
    libgtk-3-0t64 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libasound2t64 \
    libdbus-glib-1-2 \
    libxt6 \
    libnss3 \
    libnspr4 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxcursor1 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libxshmfence1 \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

# GPU rendering: stock Ubuntu Mesa, PINNED. Resolute's stock Mesa 26.0.3 is
# new enough for the WebGPU TSL passes; the Kisak PPA's 26.1.4 corrupts the
# effects path (banded gradient output while every audit still passes), so
# the PPA is deliberately NOT used. Exact pins mean an archive version bump
# fails the build loudly — re-verify a rendered FRAME before bumping them.
RUN apt-get update && apt-get install -y --no-install-recommends --allow-downgrades \
    xvfb \
    mesa-vulkan-drivers=26.0.3-1ubuntu1 mesa-libgallium=26.0.3-1ubuntu1 \
    libgl1-mesa-dri=26.0.3-1ubuntu1 libegl-mesa0=26.0.3-1ubuntu1 \
    libgbm1=26.0.3-1ubuntu1 libglx-mesa0=26.0.3-1ubuntu1 && \
    rm -rf /var/lib/apt/lists/*

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,video
ENV GALLIUM_DRIVER=d3d12
ENV LD_LIBRARY_PATH=/usr/lib/wsl/lib
ENV MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA

# Python toolchain: TTS, audio (demucs/librosa/pyworld), image, data viz,
# geometry, MIDI, vector graphics, figlet banners.
RUN apt-get update && apt-get install -y --no-install-recommends libcairo2-dev g++ python3-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --break-system-packages --no-cache-dir \
    edge-tts numpy Pillow staticmap matplotlib skyfield shapely svgwrite \
    cairosvg requests midiutil music21 librosa pyworld demucs stable-ts \
    pixelsort torchcodec diffq pyfiglet

# Puppeteer-core + Chrome — required by fetch_model.py for scraping
# NIH 3D / NASA / Smithsonian model previews. fetch_model.py resolves the
# ESM entry at /opt/render3d/node_modules/puppeteer-core and globs the
# chrome binary under /opt/render3d/.cache/puppeteer.
RUN mkdir -p /opt/render3d && cd /opt/render3d && \
    echo '{"type":"module"}' > package.json && \
    npm install puppeteer-core@22 && \
    npm install -g puppeteer@22 && \
    PUPPETEER_CACHE_DIR=/opt/render3d/.cache/puppeteer \
        npx --yes puppeteer browsers install chrome && \
    chmod -R a+rX /opt/render3d/.cache/puppeteer && \
    chown -R node:node /opt/render3d/.cache 2>/dev/null; true

# ---- Agent CLI (per-flavor) — LAST heavy layer, so all four flavors share
# every layer above this one in the build cache. Auth is bind-mounted at
# runtime by eido.py:
#   claude   → /home/node/.claude/       (host ~/.claude credentials, ro)
#   codex    → /home/node/.codex/        (host auth.json + config.toml, ro)
#   opencode → env OPENCODE_API_KEY      (passed via docker -e)
RUN set -e; case "$AGENT" in \
      claude)   npm install -g @anthropic-ai/claude-code && \
                mkdir -p /home/node/.claude && chown -R node:node /home/node/.claude ;; \
      codex)    npm install -g @openai/codex && \
                mkdir -p /home/node/.codex && chown -R node:node /home/node/.codex ;; \
      opencode) npm install -g opencode-ai && \
                mkdir -p /home/node/.config/opencode && chown -R node:node /home/node/.config ;; \
      none)     echo "render-only image (no agent CLI)" ;; \
      *)        echo "unknown AGENT='$AGENT' (use claude|codex|opencode|none)"; exit 1 ;; \
    esac

# Workspace mount point + X11 socket dir
RUN mkdir -p /workspace && chown node:node /workspace
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

# Smoke-test key binaries (build fails loudly if broken)
RUN deno --version && node --version && ffmpeg -version 2>&1 | head -1 && python3 -c "import edge_tts, librosa" 2>/dev/null || true

USER node
WORKDIR /workspace
