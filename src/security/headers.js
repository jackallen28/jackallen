// Browser security headers for every response.

export function securityHeaders(req, res, next) {
  res.set({
    // Only load scripts/styles from this site; no framing by other sites; forms only post here.
    'Content-Security-Policy': [
      "default-src 'self'",
      "script-src 'self'",
      "style-src 'self' 'unsafe-inline'", // FullCalendar sets inline styles
      "img-src 'self' data:",
      "connect-src 'self'",
      "font-src 'self' data:", // FullCalendar's arrow icons
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ].join('; '),
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'same-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
    'Cross-Origin-Opener-Policy': 'same-origin',
  });
  if (req.secure) res.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  next();
}

/** Parses "203.0.113.5, 10.0.0.0/8" into a matcher for IPv4/IPv6 addresses and IPv4 ranges. */
export function ipMatcher(list) {
  const rules = list.map((entry) => {
    const [ip, bits] = entry.split('/');
    if (bits !== undefined && ip.includes('.')) {
      const mask = Number(bits) === 0 ? 0 : (~0 << (32 - Number(bits))) >>> 0;
      return { kind: 'v4range', base: ipv4ToInt(ip) & mask, mask };
    }
    return { kind: 'exact', ip: normalise(ip) };
  });
  return (address) => {
    const ip = normalise(address || '');
    return rules.some((r) =>
      r.kind === 'exact' ? r.ip === ip : ip.includes('.') && !ip.includes(':') && (ipv4ToInt(ip) & r.mask) === r.base,
    );
  };
}

function normalise(ip) {
  return String(ip).trim().replace(/^::ffff:/, ''); // IPv4 written as IPv6
}

function ipv4ToInt(ip) {
  return ip.split('.').reduce((acc, part) => ((acc << 8) + Number(part)) >>> 0, 0);
}
