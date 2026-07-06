/**
 * Next.js Middleware - Route Protection
 *
 * Protects API routes and dashboard pages.
 * Redirects unauthenticated users to /login.
 */

import { withAuth } from "next-auth/middleware";

export default withAuth({
  pages: {
    signIn: "/login",
  },
});

export const config = {
  matcher: [
    // Protect dashboard and all API routes except auth and public endpoints
    "/dashboard/:path*",
    "/api/mistral/:path*",
    "/api/process/:path*",
    "/api/process-batch/:path*",
    "/api/batch-process-sse/:path*",
    "/api/images/:path*",
    "/api/train/:path*",
    "/api/predict/:path*",
    "/api/export-training/:path*",
    "/api/word-correction/:path*",
    "/api/training/:path*",
    "/api/training-words/:path*",
    "/api/ai-chat/:path*",
    "/api/stats/:path*",
    "/api/settings/:path*",
    "/api/logs/:path*",
  ],
};
