# Program booking system — container image.
#   docker build -t program-bookings .
#   docker run -p 3000:3000 -v bookings-data:/data --env-file .env program-bookings

FROM node:22-slim
ENV NODE_ENV=production \
    PORT=3000 \
    DATA_DIR=/data
WORKDIR /app

# better-sqlite3 ships ready-made binaries for Linux/macOS/Windows, so no compilers are needed
# (--ignore-scripts stops npm trying to rebuild it from source).
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force

COPY src ./src
COPY public ./public
COPY config ./config
COPY scripts ./scripts
COPY docs ./docs

# The SQLite database lives on a volume so bookings survive restarts and upgrades.
RUN mkdir -p /data && chown node:node /data
VOLUME ["/data"]
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "src/server.js"]
