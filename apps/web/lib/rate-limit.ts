/**
 * In-memory sliding window rate limiter
 *
 * ⚠️  IMPORTANT: This in-memory implementation is suitable for
 * single-instance deployments only. In a multi-container / production setup
 * you MUST replace the `Map`-based store with Redis (e.g. ioredis)
 * or use an API-gateway level rate limiter (Nginx, Kong, Cloudflare).
 *
 * Usage:
 *   import { rateLimit } from "@/lib/rate-limit";
 *   const { success, remaining, resetAt } = rateLimit("api-process", 10, 60);
 *   if (!success) return NextResponse.json({ error: "Too many requests" }, { status: 429 });
 */

interface RateLimitEntry {
  timestamps: number[];
}

// ── Store ──────────────────────────────────────────────────────────────
// In-memory store (for production, use Redis)
const store = new Map<string, RateLimitEntry>();

// Cleanup old entries every 5 minutes
const CLEANUP_INTERVAL = 5 * 60 * 1000;
let lastCleanup = Date.now();

function cleanup(now: number) {
  if (now - lastCleanup < CLEANUP_INTERVAL) return;
  lastCleanup = now;

  for (const [key, entry] of store.entries()) {
    // Remove entries older than 1 hour with no recent activity
    if (entry.timestamps.length === 0 || entry.timestamps[0] < now - 3600000) {
      store.delete(key);
    }
  }
}

/**
 * Check and apply rate limit
 *
 * @param key - Unique identifier (e.g., IP address or user ID)
 * @param maxRequests - Maximum requests in the window
 * @param windowSeconds - Time window in seconds
 * @returns Object with success status, remaining requests, and reset time
 */
export function rateLimit(
  key: string,
  maxRequests: number = 100,
  windowSeconds: number = 60
): { success: boolean; remaining: number; resetAt: number } {
  const now = Date.now();
  cleanup(now);

  const windowMs = windowSeconds * 1000;
  const windowStart = now - windowMs;

  let entry = store.get(key);
  if (!entry) {
    entry = { timestamps: [] };
    store.set(key, entry);
  }

  // Remove timestamps outside the current window
  entry.timestamps = entry.timestamps.filter((t) => t > windowStart);

  if (entry.timestamps.length >= maxRequests) {
    const oldestInWindow = entry.timestamps[0];
    return {
      success: false,
      remaining: 0,
      resetAt: oldestInWindow + windowMs,
    };
  }

  // Add current request timestamp
  entry.timestamps.push(now);

  return {
    success: true,
    remaining: maxRequests - entry.timestamps.length,
    resetAt: now + windowMs,
  };
}

/** Standard rate-limit headers attached to every response. */
const RATE_LIMIT_HEADERS = {
  "X-RateLimit-Policy": "1;w=60",          // 1 request per second burst, 60s window
  "X-RateLimit-Limit": "100",
} as const;

/**
 * Apply rate limiting to a Next.js API route.
 * Returns a 429 response if rate limit exceeded, or null if OK.
 */
export function withRateLimit(
  request: Request,
  maxRequests: number = 100,
  windowSeconds: number = 60
): { limited: boolean; response?: Response } {
  // Use IP or a fallback identifier
  const forwarded = request.headers.get("x-forwarded-for");
  const ip = forwarded ? forwarded.split(",")[0].trim() : "unknown";

  const result = rateLimit(ip, maxRequests, windowSeconds);

  if (!result.success) {
    return {
      limited: true,
      response: Response.json(
        {
          error: "Too many requests",
          remaining: result.remaining,
          resetAt: new Date(result.resetAt).toISOString(),
        },
        {
          status: 429,
          headers: {
            "Content-Type": "application/json",
            "Retry-After": String(Math.ceil((result.resetAt - Date.now()) / 1000)),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": new Date(result.resetAt).toISOString(),
            ...RATE_LIMIT_HEADERS,
          },
        }
      ),
    };
  }

  return { limited: false };
}

/**
 * Attach standard rate-limit headers to a successful response.
 * Call this on every non-limited API response for consistency.
 */
export function attachRateLimitHeaders(
  response: Response,
  remaining: number,
  resetAt: number
): Response {
  const newHeaders = new Headers(response.headers);
  newHeaders.set("X-RateLimit-Remaining", String(remaining));
  newHeaders.set("X-RateLimit-Reset", new Date(resetAt).toISOString());
  newHeaders.set("X-RateLimit-Limit", "100");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}
