/**
 * Redis-backed rate limiter for production use
 *
 * This module provides a Redis-based sliding window rate limiter that
 * works across multiple instances/containers. Use this instead of the
 * in-memory rate-limiter (rate-limit.ts) for production deployments.
 *
 * Requirements:
 *   - Redis server accessible via REDIS_URL env var
 *   - npm package: ioredis (already available via @upstash/redis or install separately)
 *
 * Usage:
 *   import { redisRateLimit } from "@/lib/rate-limit-redis";
 *   const { success, remaining, resetAt } = await redisRateLimit("user:123", 10, 60);
 */

import type { Redis } from "ioredis";

let redisClient: Redis | null = null;

/**
 * Initialize the Redis client. Call once at app startup.
 * Falls back to in-memory limiter if Redis is unavailable.
 */
export async function initRedisRateLimiter(): Promise<void> {
  try {
    const redisUrl = process.env.REDIS_URL || process.env.KV_URL;
    if (!redisUrl) {
      console.warn("[rate-limit] REDIS_URL not set — falling back to in-memory limiter");
      return;
    }
    // Dynamic import to avoid bundling ioredis when not needed
    const { default: Redis } = await import("ioredis");
    redisClient = new Redis(redisUrl, {
      maxRetriesPerRequest: 3,
      retryStrategy(times) {
        return Math.min(times * 200, 2000);
      },
    });
    redisClient.on("error", (err) => {
      console.error("[rate-limit] Redis connection error:", err.message);
      redisClient = null;
    });
    console.log("[rate-limit] Redis-backed rate limiter initialized");
  } catch (err) {
    console.warn("[rate-limit] Failed to initialize Redis rate limiter:", (err as Error).message);
    redisClient = null;
  }
}

/**
 * Redis-based sliding window rate limiter.
 *
 * Uses a sorted set (ZSET) where:
 *   - Score = timestamp of the request
 *   - Member = unique request ID (timestamp + random)
 *
 * This provides accurate sliding window behavior across multiple instances.
 */
export async function redisRateLimit(
  key: string,
  maxRequests: number = 100,
  windowSeconds: number = 60
): Promise<{ success: boolean; remaining: number; resetAt: number }> {
  if (!redisClient) {
    // Fallback: import in-memory limiter
    const { rateLimit } = await import("@/lib/rate-limit");
    return rateLimit(key, maxRequests, windowSeconds);
  }

  const now = Date.now();
  const windowStart = now - windowSeconds * 1000;
  const memberKey = `${now}-${Math.random().toString(36).slice(2)}`;

  const pipeline = redisClient.pipeline();

  // Remove old entries outside the window
  pipeline.zremrangebyscore(key, 0, windowStart);

  // Count current entries
  pipeline.zcard(key);

  // Add current request
  pipeline.zadd(key, now, memberKey);

  // Set expiry so keys are auto-cleaned
  pipeline.expire(key, windowSeconds + 10);

  const results = await pipeline.exec();

  const currentCount = results?.[1]?.[1] as number | undefined;
  const count = (currentCount || 0) + 1; // +1 for the just-added request

  if (count > maxRequests) {
    // Find the oldest entry to calculate reset time
    const oldest = await redisClient.zrange(key, 0, 0, "WITHSCORES");
    const oldestTimestamp = oldest?.[1] ? parseFloat(oldest[1]) : now;
    return {
      success: false,
      remaining: 0,
      resetAt: oldestTimestamp + windowSeconds * 1000,
    };
  }

  return {
    success: true,
    remaining: maxRequests - count,
    resetAt: now + windowSeconds * 1000,
  };
}

/**
 * Close the Redis connection. Call on app shutdown.
 */
export async function closeRedisRateLimiter(): Promise<void> {
  if (redisClient) {
    await redisClient.quit();
    redisClient = null;
  }
}
