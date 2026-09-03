// Where generated STL/PNG/SCAD files live.
//   local -> DATA_DIR/files, served by this process at /files/<key>
//   s3    -> any S3-compatible bucket (AWS S3, Cloudflare R2, Backblaze B2)
import fs from 'node:fs/promises';
import path from 'node:path';
import { config } from './config.js';

const filesDir = path.join(config.storage.dataDir, 'files');

const CONTENT_TYPES = {
  '.stl': 'model/stl',
  '.png': 'image/png',
  '.scad': 'text/plain; charset=utf-8',
  '.json': 'application/json',
};

export function contentTypeFor(key) {
  return CONTENT_TYPES[path.extname(key).toLowerCase()] || 'application/octet-stream';
}

let s3Client = null;
async function getS3() {
  if (s3Client) return s3Client;
  const { S3Client } = await import('@aws-sdk/client-s3');
  const { s3 } = config.storage;
  s3Client = new S3Client({
    region: s3.region,
    endpoint: s3.endpoint,
    forcePathStyle: Boolean(s3.endpoint),
    credentials: s3.accessKeyId
      ? { accessKeyId: s3.accessKeyId, secretAccessKey: s3.secretAccessKey }
      : undefined,
  });
  return s3Client;
}

/**
 * Store a file and return a URL the browser can open.
 * @param {string} key e.g. "s_abc/j_123/model.stl"
 * @param {Buffer|string} body
 * @param {{download?: string}} opts filename to force as a download
 */
export async function putFile(key, body, opts = {}) {
  const safeKey = key.replace(/[^a-zA-Z0-9._/-]/g, '_');
  if (config.storage.driver === 's3') {
    const { PutObjectCommand } = await import('@aws-sdk/client-s3');
    const client = await getS3();
    await client.send(new PutObjectCommand({
      Bucket: config.storage.s3.bucket,
      Key: safeKey,
      Body: body,
      ContentType: contentTypeFor(safeKey),
      ContentDisposition: opts.download ? `attachment; filename="${opts.download}"` : undefined,
    }));
    if (config.storage.s3.publicBaseUrl) return `${config.storage.s3.publicBaseUrl}/${safeKey}`;
    const { GetObjectCommand } = await import('@aws-sdk/client-s3');
    const { getSignedUrl } = await import('@aws-sdk/s3-request-presigner');
    return getSignedUrl(client, new GetObjectCommand({ Bucket: config.storage.s3.bucket, Key: safeKey }), {
      expiresIn: config.storage.s3.signedUrlTtlSec,
    });
  }

  const dest = path.join(filesDir, safeKey);
  await fs.mkdir(path.dirname(dest), { recursive: true });
  await fs.writeFile(dest, body);
  return `${config.publicUrl}/files/${safeKey}`;
}

// Local-driver reads for the /files route. Returns null when the key escapes
// the files directory or does not exist.
export async function readLocalFile(key) {
  const dest = path.join(filesDir, key);
  if (!dest.startsWith(filesDir + path.sep)) return null;
  try {
    return await fs.readFile(dest);
  } catch {
    return null;
  }
}
