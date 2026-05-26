"use client";

/**
 * SessionProvider wrapper component
 * Wraps the app with NextAuth SessionProvider for client-side auth access
 */

import { SessionProvider } from "next-auth/react";
import { ReactNode } from "react";

export function AuthProvider({ children }: { children: ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}
