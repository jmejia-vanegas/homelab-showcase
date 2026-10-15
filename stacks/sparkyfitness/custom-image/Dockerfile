# Local patches on top of the upstream SparkyFitness server image.
#
# 1. labelScanService.ts — adds an FDA Daily Value reference table to the
#    label-scan prompt so a local/small vision model can convert %DV-only
#    nutrients to absolute amounts via simple arithmetic instead of needing
#    to recall the reference table from training. See that file for the
#    full explanation.
#
# 2. providerDispatch.ts — two fixes for Ollama + images, both found while
#    debugging meal-photo scanning against the local hass-ollama instance:
#
#    a. Backports upstream commit 326f1428 ("fix for chat bot image
#       processing", 2026-08-28), which had not made it into a release yet
#       as of this image's build date (base image built 2026-08-27). Without
#       it, sending an image together with a JSON Schema to Ollama makes it
#       grammar-constrain generation against the full schema, which reliably
#       crashes llama.cpp's grammar engine ("Unexpected empty grammar
#       stack..."). Verified by direct testing that even the upstream fix's
#       looser `format: 'json'` still triggers the same crash class when an
#       image is present, so this patch goes further than upstream and drops
#       the `format` field entirely for Ollama, relying on the
#       prompt-embedded schema text alone (matches an open, unresolved class
#       of llama.cpp grammar-engine bugs, e.g. ggml-org/llama.cpp#27619 — not
#       specific to this project).
#
#    b. Downscales images to a max 1568px edge before sending to Ollama
#       (new sharp dependency below). Mobile clients only reduce JPEG
#       quality, never pixel dimensions, so a phone photo can be full native
#       camera resolution. Verified by direct testing that an image that
#       large reliably corrupts this GPU's CUDA/llama.cpp context (garbled
#       "?????" output, persisting until the container is restarted) rather
#       than failing cleanly — a shared 8GB card, also serving Frigate NVR
#       and Home Assistant voice, doesn't have the VRAM headroom for it.
#
#    See the comments on buildOllamaRequest() and downscaleImagesForOllama()
#    in that file for details. Drop the corresponding piece once a released
#    upstream version includes it.
#
# Maintenance note: this pins to whatever `latest` resolved to at build time
# and does NOT auto-update. To pick up a newer upstream release, re-run:
#   docker build -t sparkyfitness_server:dv-patch --pull .
#   docker compose up -d sparkyfitness-server
# in this directory. Before rebuilding, check whether each patch is still
# needed against the new base image (upstream may have shipped its own fix
# by then) and drop the corresponding COPY line if so.
FROM codewithcj/sparkyfitness_server:latest

# sharp ships prebuilt binaries for linux-x64 musl (this base is Alpine), so
# no build toolchain is needed. Installed in a scratch directory rather than
# in place: the existing package.json/lock use `workspace:*` deps that only
# resolve inside the monorepo's original workspace, so any npm install run
# against them here fails with EUNSUPPORTEDPROTOCOL. A standalone install
# has no such deps to reconcile; its node_modules/sharp is then copied
# straight into the app's node_modules.
RUN mkdir /tmp/sharp-install \
    && cd /tmp/sharp-install \
    && npm init -y \
    && npm install sharp \
    && cp -r node_modules/. /app/SparkyFitnessServer/node_modules/ \
    && cd / && rm -rf /tmp/sharp-install

COPY labelScanService.ts /app/SparkyFitnessServer/services/labelScanService.ts
COPY providerDispatch.ts /app/SparkyFitnessServer/ai/providerDispatch.ts
