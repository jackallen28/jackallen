import 'dotenv/config';
import path from 'node:path';

const bool = (v, d = false) => (v == null ? d : /^(1|true|yes|on)$/i.test(String(v)));
const int = (v, d) => (Number.isFinite(Number(v)) ? Number(v) : d);
const list = (v) => String(v || '').split(',').map((s) => s.trim()).filter(Boolean);

export const config = {
  port: int(process.env.PORT, 8080),
  publicUrl: (process.env.PUBLIC_URL || `http://localhost:${int(process.env.PORT, 8080)}`).replace(/\/$/, ''),

  // Comma-separated list of sites allowed to embed the widget. "*" allows any
  // origin (fine while testing, tighten before you go live).
  allowedOrigins: list(process.env.ALLOWED_ORIGINS) .length ? list(process.env.ALLOWED_ORIGINS) : ['*'],

  brand: {
    name: process.env.BRAND_NAME || 'CAD Quote Bot',
    accent: process.env.BRAND_ACCENT || '#FF6A1A',
  },

  anthropic: {
    apiKey: process.env.ANTHROPIC_API_KEY,
    model: process.env.ANTHROPIC_MODEL || 'claude-opus-5',
  },

  openscad: {
    bin: process.env.OPENSCAD_BIN || 'openscad',
    // Wrap in xvfb-run when the container has no GL context (Debian/Ubuntu images).
    useXvfb: bool(process.env.OPENSCAD_XVFB, true),
    timeoutMs: int(process.env.OPENSCAD_TIMEOUT_MS, 90_000),
    imgSize: process.env.OPENSCAD_IMGSIZE || '1400,1050',
  },

  storage: {
    // 'local' writes into DATA_DIR and serves via /files. 's3' works with AWS S3,
    // Cloudflare R2, Backblaze B2 — anything S3-compatible.
    driver: (process.env.STORAGE_DRIVER || 'local').toLowerCase(),
    dataDir: path.resolve(process.env.DATA_DIR || './data'),
    s3: {
      bucket: process.env.S3_BUCKET,
      region: process.env.S3_REGION || 'auto',
      endpoint: process.env.S3_ENDPOINT || undefined,
      accessKeyId: process.env.S3_ACCESS_KEY_ID,
      secretAccessKey: process.env.S3_SECRET_ACCESS_KEY,
      publicBaseUrl: (process.env.S3_PUBLIC_BASE_URL || '').replace(/\/$/, ''),
      signedUrlTtlSec: int(process.env.S3_SIGNED_URL_TTL, 60 * 60 * 24 * 7),
    },
  },

  mail: {
    // Provider is picked automatically: Resend if RESEND_API_KEY is set,
    // otherwise SMTP if SMTP_HOST is set, otherwise console logging.
    resendApiKey: process.env.RESEND_API_KEY,
    smtp: {
      host: process.env.SMTP_HOST,
      port: int(process.env.SMTP_PORT, 587),
      secure: bool(process.env.SMTP_SECURE, false),
      user: process.env.SMTP_USER,
      pass: process.env.SMTP_PASS,
    },
    from: process.env.MAIL_FROM || 'CAD Quote Bot <quotes@example.com>',
    // Where quote requests land — this is your inbox.
    to: list(process.env.QUOTE_NOTIFY_EMAIL),
    replyToOwner: process.env.QUOTE_REPLY_TO || undefined,
    sendCustomerCopy: bool(process.env.SEND_CUSTOMER_COPY, true),
  },

  limits: {
    maxMessageChars: int(process.env.MAX_MESSAGE_CHARS, 1200),
    maxGenerationsPerSession: int(process.env.MAX_GENERATIONS_PER_SESSION, 6),
    maxSessionsPerIpPerHour: int(process.env.MAX_SESSIONS_PER_IP_HOUR, 12),
    maxMessagesPerIpPerHour: int(process.env.MAX_MESSAGES_PER_IP_HOUR, 200),
    sessionTtlMs: int(process.env.SESSION_TTL_HOURS, 72) * 3600_000,
  },
};

export function assertConfig() {
  const problems = [];
  if (!config.anthropic.apiKey) problems.push('ANTHROPIC_API_KEY is not set');
  if (!config.mail.to.length) problems.push('QUOTE_NOTIFY_EMAIL is not set (you will not receive quote requests)');
  if (config.storage.driver === 's3' && !config.storage.s3.bucket) problems.push('STORAGE_DRIVER=s3 but S3_BUCKET is not set');
  return problems;
}
