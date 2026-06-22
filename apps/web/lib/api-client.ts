/**
 * Shared API client with retry logic, error handling, and abort support.
 *
 * Usage:
 *   import { apiFetch } from "@/lib/api-client";
 *   const data = await apiFetch("/api/stats", { retries: 3 });
 */

interface ApiFetchOptions extends RequestInit {
  retries?: number;
  retryDelay?: number;
  timeout?: number;
}

/**
 * Fetch wrapper with automatic retry, timeout, and error normalization.
 *
 * @param url - API endpoint (relative to app base URL)
 * @param options - Fetch options plus retry/timeout settings
 * @returns Parsed JSON response
 * @throws {ApiError} on failure after all retries exhausted
 */
export async function apiFetch<T = unknown>(
  url: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const { retries = 2, retryDelay = 1000, timeout = 15000, ...fetchOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, {
        ...fetchOptions,
        signal: controller.signal,
      });

      if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new ApiError(
          response.status,
          `API error ${response.status}: ${body || response.statusText}`,
          body
        );
      }

      const data = await response.json();
      return data as T;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Don't retry on client errors (4xx) or abort
      if (lastError instanceof ApiError && lastError.status >= 400 && lastError.status < 500) {
        break;
      }
      if (lastError.name === "AbortError") {
        break;
      }

      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, retryDelay * (attempt + 1)));
      }
    }
  }

  clearTimeout(timeoutId);
  throw lastError || new Error("API request failed");
}

/**
 * Custom error class for API errors with status code and response body.
 */
export class ApiError extends Error {
  status: number;
  body: string;

  constructor(status: number, message: string, body: string = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/**
 * Fetch with rate limit headers attached.
 * Returns both data and rate limit info for UI display.
 */
export async function apiFetchWithRateLimit<T = unknown>(
  url: string,
  options: ApiFetchOptions = {}
): Promise<{ data: T; rateLimit: { remaining: number; resetAt: string; limit: number } }> {
  const response = await fetch(url, {
    ...options,
    headers: options.headers,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new ApiError(response.status, `API error ${response.status}`, body);
  }

  const data = await response.json();
  const remaining = parseInt(response.headers.get("X-RateLimit-Remaining") || "100", 10);
  const resetAt = response.headers.get("X-RateLimit-Reset") || "";
  const limit = parseInt(response.headers.get("X-RateLimit-Limit") || "100", 10);

  return {
    data: data as T,
    rateLimit: { remaining, resetAt, limit },
  };
}
