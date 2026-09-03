# OpenSCAD is a native binary, so this service needs a container — not a
# serverless function. Any host that runs a Dockerfile will do.
FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      openscad \
      xvfb \
      libgl1 \
      ca-certificates \
      fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server/package.json server/package-lock.json ./server/
RUN cd server && npm ci --omit=dev --no-audit --no-fund

COPY server ./server
COPY embed ./embed

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
