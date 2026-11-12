# Eidoverse render sandbox, Blender edition: Blender 5.2 (EEVEE) + Mesa D3D12 +
# Deno (canvas scenes, parity tools) + the full audio/asset toolchain.
# One Dockerfile, four flavors:
#
#   docker build -f docker/Dockerfile --build-arg AGENT=none     -t eidoverse-blender:render docker
#   docker build -f docker/Dockerfile --build-arg AGENT=claude   -t eidoverse-blender:claude docker
#   docker build -f docker/Dockerfile --build-arg AGENT=codex    -t eidoverse-blender:codex docker
#   docker build -f docker/Dockerfile --build-arg AGENT=opencode -t eidoverse-blender:opencode docker
#
# Build context = the docker/ dir (small, so BuildKit never walks the repo).
# The repo itself is NOT baked in: eido_blender.py mounts it at /workspace at
# runtime, so toolkit changes never require a rebuild.
#
# GPU path on Windows/WSL2: Blender's OpenGL -> Mesa's D3D12 Gallium driver
# (through the software-presentation loader under Xvfb) -> /dev/dxg -> the host
# NVIDIA driver. EEVEE renders on the GPU; only the finished pixels cross
# Xvfb. On native Linux with an NVIDIA GPU, the NVIDIA container toolkit's
# GLX/EGL libraries take that role instead.

# ---------------------------------------------------------------------------
# Stage 1: Blender + the GPU path. Small on purpose, so the GPU route can be
# checked on its own:  docker build --target blender-core -t eidoverse-blender:core docker
# Ubuntu 26.04 LTS, not :rolling. The WebGPU edition rode :rolling for a newer
# Mesa; Blender's OpenGL path needs no bleeding edge, and an LTS base keeps the
# pins below resolvable for years (rolling dropped the WebGPU edition's pins).
FROM ubuntu:26.04 AS blender-core
ENV DEBIAN_FRONTEND=noninteractive

# GPU rendering: stock Ubuntu Mesa, PINNED to the version whose EEVEE frames
# were checked (docker/blender_gpu_check.py). Xvfb gives Blender the X display
# it opens even in background mode.
ARG MESA=26.0.8-1ubuntu0.3
RUN apt-get update && apt-get install -y --no-install-recommends --allow-downgrades \
    ca-certificates curl xz-utils \
    xvfb xauth \
    libegl1 libgl1 libglx0 libglvnd0 mesa-utils \
    mesa-vulkan-drivers=${MESA} mesa-libgallium=${MESA} \
    libgl1-mesa-dri=${MESA} libegl-mesa0=${MESA} \
    libgbm1=${MESA} libglx-mesa0=${MESA} \
    libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libxkbcommon-x11-0 \
    libsm6 libice6 libxext6 libxrandr2 libxcursor1 libxinerama1 libwayland-client0 \
    libwayland-cursor0 libwayland-egl1 libdecor-0-0 libdbus-1-3 libfontconfig1 libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Blender 5.2 LTS, the official Linux build (the edition's tested version), from
# Blender's official mirrors (download.blender.org itself refuses scripted
# downloads), checked against the SHA-256 that Blender publishes with the release.
ARG BLENDER_VERSION=5.2.0
ARG BLENDER_SHA256=96f6c181a30f4950607839dc84d42a354b250d8a0231b098b59b7bc69c351c48
RUN f="Blender${BLENDER_VERSION%.*}/blender-${BLENDER_VERSION}-linux-x64.tar.xz"; \
    for m in https://mirrors.ocf.berkeley.edu/blender/release https://ftp.nluug.nl/pub/graphics/blender/release \
             https://mirror.clarkson.edu/blender/release; do \
        curl -fsSL "$m/$f" -o /tmp/blender.tar.xz && break; done && \
    echo "${BLENDER_SHA256}  /tmp/blender.tar.xz" | sha256sum -c - && \
    tar -xJf /tmp/blender.tar.xz -C /opt && \
    mv "/opt/blender-${BLENDER_VERSION}-linux-x64" /opt/blender && \
    ln -s /opt/blender/blender /usr/local/bin/blender && \
    rm /tmp/blender.tar.xz

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,video
ENV GALLIUM_DRIVER=d3d12
ENV LD_LIBRARY_PATH=/usr/lib/wsl/lib
ENV MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA

# ---------------------------------------------------------------------------
# Stage 2: the production sandbox: everything a scene and an agent use.
FROM blender-core AS sandbox
ARG AGENT=none

# Node.js 22 LTS (agent CLIs + puppeteer), with its bundled npm. (Node 20 reached end of life in 2026, and
# npm@latest now refuses it, so `npm install -g npm@latest` on 20 fails the build.)
RUN apt-get update && apt-get install -y --no-install-recommends gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && rm -rf /var/lib/apt/lists/* && \
    node --version && npm --version

# Non-root user early so chown works later
RUN useradd -m -s /bin/bash node

# Deno: runs the canvas screen scenes (blender/eidoblend/media/js/*.mjs drive the engine's own drawing code), the
# book and parole exporters, and the parity tools. PINNED like the WebGPU edition's.
RUN apt-get update && apt-get install -y --no-install-recommends unzip && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh -s -- -y v2.8.1

# Static ffmpeg with nvenc support (BtbN GPL build), PINNED to a dated autobuild: "latest" tracks the newest nvenc
# SDK, which can demand a newer NVIDIA driver than the host has. Bump deliberately, after checking your driver.
RUN curl -fsSL https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-03-31-13-11/ffmpeg-N-123777-g53537f6cf5-linux64-gpl.tar.xz \
        -o /tmp/ffmpeg.tar.xz && \
    tar -xJf /tmp/ffmpeg.tar.xz -C /tmp && \
    install -m 0755 /tmp/ffmpeg-N-123777-g53537f6cf5-linux64-gpl/bin/ffmpeg  /usr/local/bin/ffmpeg && \
    install -m 0755 /tmp/ffmpeg-N-123777-g53537f6cf5-linux64-gpl/bin/ffprobe /usr/local/bin/ffprobe && \
    rm -rf /tmp/ffmpeg.tar.xz /tmp/ffmpeg-N-123777-g53537f6cf5-linux64-gpl

# Custom display fonts (OFL; used by extruded type and the canvas screens: see AGENTS.md font rules)
COPY fonts/*.ttf /usr/share/fonts/truetype/custom/
RUN chmod 644 /usr/share/fonts/truetype/custom/*.ttf

# System fonts + fontconfig + FluidSynth + the shared-library set headless Chrome (fetch_model.py previews) needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip git fontconfig \
    fonts-dejavu-core fonts-liberation fonts-noto-mono fonts-noto-core fonts-noto-cjk fonts-noto-color-emoji \
    fonts-noto-extra fluidsynth fluid-soundfont-gm \
    libgtk-3-0t64 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libasound2t64 libdbus-glib-1-2 libxt6 libnss3 libnspr4 \
    libcups2 libdrm2 libxcomposite1 libxdamage1 libxtst6 libgbm1 libpango-1.0-0 libcairo2 libatspi2.0-0 \
    libxshmfence1 \
    && fc-cache -f && rm -rf /var/lib/apt/lists/*

# Python toolchain (system Python, for the repo-root tools): TTS, audio (demucs/librosa/pyworld), image, data viz,
# geometry, MIDI, vector graphics, figlet banners.
RUN apt-get update && apt-get install -y --no-install-recommends libcairo2-dev g++ python3-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --break-system-packages --no-cache-dir \
    edge-tts numpy Pillow staticmap matplotlib skyfield shapely svgwrite \
    cairosvg requests midiutil music21 librosa pyworld demucs stable-ts \
    pixelsort torchcodec diffq pyfiglet opencv-python-headless

# Puppeteer-core + Chrome, required by fetch_model.py for scraping NIH 3D / NASA / Smithsonian model previews.
RUN mkdir -p /opt/render3d && cd /opt/render3d && \
    echo '{"type":"module"}' > package.json && \
    npm install puppeteer-core@22 && \
    npm install -g puppeteer@22 && \
    PUPPETEER_CACHE_DIR=/opt/render3d/.cache/puppeteer \
        npx --yes puppeteer browsers install chrome && \
    chmod -R a+rX /opt/render3d/.cache/puppeteer && \
    chown -R node:node /opt/render3d/.cache 2>/dev/null; true

# ---- Agent CLI (per flavor): the LAST heavy layer, so all four flavors share every layer above it. Auth is
# bind-mounted at runtime by eido_docker.py:
#   claude   -> /home/node/.claude/       (host ~/.claude credentials, ro)
#   codex    -> /home/node/.codex/        (host auth.json + config.toml, ro)
#   opencode -> env OPENCODE_API_KEY      (passed via docker -e)
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

# SeedThree (github.com/SkyeShark/SeedThree, MIT), its `blender` branch: the Blender add-on behind make_seed_tree,
# with the app's textures. eidoblend.trees finds it through SEEDTHREE_DIR.
ARG SEEDTHREE_REF=blender
RUN curl -fsSL "https://github.com/SkyeShark/SeedThree/archive/refs/heads/${SEEDTHREE_REF}.tar.gz" | tar -xz -C /opt \
 && mv "/opt/SeedThree-${SEEDTHREE_REF}" /opt/SeedThree \
 && rm -rf /opt/SeedThree/node_modules \
 && chown -R node:node /opt/SeedThree
ENV SEEDTHREE_DIR=/opt/SeedThree

# Workspace mount point + X11 socket dir
RUN mkdir -p /workspace && chown node:node /workspace
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

USER node
# The VRM Add-on for Blender (MIT / GPL-3.0), installed by Blender's own extension command into node's user folder,
# where run_blender.sh finds it and copies it into each run's isolated sandbox.
RUN blender --online-mode --command extension install --sync --enable vrm 2>&1 | tail -1 && \
    test -f /home/node/.config/blender/5.2/extensions/blender_org/vrm/blender_manifest.toml

# Smoke-test key binaries (the build fails loudly if one is broken)
RUN blender --version | head -1 && deno --version | head -1 && node --version && ffmpeg -version | head -1 && \
    python3 -c "import edge_tts, librosa, numpy, PIL; print('python tools ok')"

WORKDIR /workspace
