/**
 * Next.js Middleware - Route Protection
 *
 * Protects all application pages and API routes.
 * The root page (/) is the main app interface and must be authenticated.
 * Redirects unauthenticated users to /login.
 *
 * Public routes (excluded from protection):
 * - /login — sign-in page
 * - /api/auth/* — NextAuth endpoints
 * - /api/health — health check
 * - /api/init-data — initial data bootstrap
 * - /api/preview/* — public document preview
 * - /api/auth/seed — user seeding (dev only)
 */

import { withAuth } from "next-auth/middleware";

export default withAuth({
  pages: {
    signIn: "/login",
  },
});

export const config = {
  matcher: [
    // Protect root page — it IS the main application
    "/",
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
    "/api/rate-limit-example/:path*",
    "/api/pdf-pages/:path*",
    "/api/extract-page-number/:path*",
  ],
};
