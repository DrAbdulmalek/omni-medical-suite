/**
 * Rate Limiting Example API Route
 * Demonstrates how to protect an API endpoint with rate limiting
 */

import { NextResponse } from "next/server";
import { withRateLimit } from "@/lib/rate-limit";

export async function GET(request: Request) {
  // Allow 10 requests per 60 seconds
  const { limited, response } = withRateLimit(request, 10, 60);

  if (limited && response) {
    return response;
  }

  return NextResponse.json({
    message: "Request successful",
    timestamp: new Date().toISOString(),
  });
}

export async function POST(request: Request) {
  // Stricter rate limit for mutations: 5 per 60 seconds
  const { limited, response } = withRateLimit(request, 5, 60);

  if (limited && response) {
    return response;
  }

  try {
    const body = await request.json();
    return NextResponse.json({
      message: "Data processed successfully",
      received: body,
      timestamp: new Date().toISOString(),
    });
  } catch {
    return NextResponse.json(
      { error: "Invalid request body" },
      { status: 400 }
    );
  }
}
