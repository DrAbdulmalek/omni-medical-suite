/**
 * NextAuth.js v4 Configuration for Medical Document Processor
 *
 * Features:
 * - Credentials-based authentication with bcrypt
 * - Account lockout after 5 failed attempts (15 min cooldown)
 * - JWT-based sessions with role information
 * - Audit logging for login events
 */

import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import { PrismaAdapter } from "@auth/prisma-adapter";
import { prisma } from "@/lib/db";

// Extend NextAuth types (see src/types/next-auth.d.ts)

export const authOptions: NextAuthOptions = {
  adapter: PrismaAdapter(prisma),

  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.username || !credentials?.password) {
          throw new Error("Missing credentials");
        }

        const user = await prisma.user.findUnique({
          where: { username: credentials.username },
        });

        if (!user) {
          throw new Error("Invalid username or password");
        }

        // Check account lockout
        if (user.lockedUntil && new Date(user.lockedUntil) > new Date()) {
          const minsLeft = Math.ceil(
            (new Date(user.lockedUntil).getTime() - Date.now()) / 60000
          );
          throw new Error(
            `Account locked. Try again in ${minsLeft} minute(s).`
          );
        }

        // Reset lockout if cooldown period has passed
        if (user.lockedUntil && new Date(user.lockedUntil) <= new Date()) {
          await prisma.user.update({
            where: { id: user.id },
            data: { failedAttempts: 0, lockedUntil: null },
          });
        }

        // Verify password with bcrypt
        const bcrypt = await import("bcryptjs");
        const isValid = await bcrypt.compare(credentials.password, user.password);

        if (!isValid) {
          // Increment failed attempts
          const newAttempts = (user.failedAttempts || 0) + 1;
          const updateData: Record<string, unknown> = {
            failedAttempts: newAttempts,
          };

          // Lock account after 5 failed attempts
          if (newAttempts >= 5) {
            updateData.lockedUntil = new Date(Date.now() + 15 * 60 * 1000); // 15 minutes
          }

          await prisma.user.update({
            where: { id: user.id },
            data: updateData,
          });

          throw new Error("Invalid username or password");
        }

        // Successful login — reset failed attempts
        await prisma.user.update({
          where: { id: user.id },
          data: { failedAttempts: 0, lockedUntil: null, lastLogin: new Date() },
        });

        return {
          id: user.id,
          name: user.username,
          role: user.role,
        };
      },
    }),
  ],

  session: {
    strategy: "jwt",
    maxAge: 24 * 60 * 60, // 24 hours
  },

  pages: {
    signIn: "/login",
  },

  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.role = (user as { role: string }).role;
        token.id = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as { id: string }).id = token.id as string;
        (session.user as { role: string }).role = token.role as string;
      }
      return session;
    },
  },

  secret: process.env.NEXTAUTH_SECRET,
};
