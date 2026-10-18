// Simple in-memory rate limiter: at most `max` hits per key within `windowMs`.
// Enough for one server process (which is how this app runs).

export function createLimiter({ windowMs, max }) {
  const hits = new Map(); // key → [timestamps]

  function prune(key, now) {
    const list = (hits.get(key) || []).filter((t) => now - t < windowMs);
    if (list.length) hits.set(key, list);
    else hits.delete(key);
    return list;
  }

  return {
    /** Records a hit. Returns { allowed, retryAfterSeconds }. */
    hit(key, now = Date.now()) {
      const list = prune(key, now);
      if (list.length >= max) {
        return { allowed: false, retryAfterSeconds: Math.ceil((windowMs - (now - list[0])) / 1000) };
      }
      list.push(now);
      hits.set(key, list);
      return { allowed: true, retryAfterSeconds: 0 };
    },
    /** True if the key is already at the limit (without recording a hit). */
    blocked(key, now = Date.now()) {
      return prune(key, now).length >= max;
    },
    reset(key) {
      hits.delete(key);
    },
  };
}

/** Express middleware: 429 once an IP goes over the limit. */
export function limitByIp(limiter, message = 'Too many requests — please wait a few minutes and try again.') {
  return (req, res, next) => {
    const { allowed, retryAfterSeconds } = limiter.hit(req.ip || 'unknown');
    if (allowed) return next();
    res.set('Retry-After', String(retryAfterSeconds));
    res.status(429).json({ error: message });
  };
}
