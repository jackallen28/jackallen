# OpenSCAD is a native binary, so this service needs a container — not a
# serverless function. Any host that runs a Dockerfile will do.
FROM node:22-bookworm-slim

# xauth is required by xvfb-run and is NOT a dependency of the xvfb package —
# without it every preview render fails. The mesa packages give OpenSCAD a
# software GL renderer inside the virtual display; without them the STL still
# exports but the preview image does not.
RUN apt-get update && apt-get install -y --no-install-recommends \
      openscad \
      xvfb \
      xauth \
      libgl1 \
      libglu1-mesa \
      libgl1-mesa-dri \
      ca-certificates \
      fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server/package.json server/package-lock.json ./server/
RUN cd server && npm ci --omit=dev --no-audit --no-fund

COPY server ./server
COPY embed ./embed

# Preview renders in the widget's own palette — white ground, grey part, orange
# cut faces — instead of OpenSCAD's default blue and orange. OpenSCAD only reads
# colour schemes from its install directory, hence the copy.
COPY server/assets/openscad-colorscheme.json /usr/share/openscad/color-schemes/render/quotebot.json

ENV NODE_ENV=production \
    PORT=8080 \
    DATA_DIR=/data

RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown -R app:app /data /app

# Starts as root only long enough to take ownership of the mounted disk; the
# entrypoint drops to the `app` user before node runs.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||8080)+'/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["node", "server/src/index.js"]
