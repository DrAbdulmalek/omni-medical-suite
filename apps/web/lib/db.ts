import { PrismaClient } from '@prisma/client'

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined
}

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    // Only log queries in development — never in production
    // to avoid leaking PHI (Protected Health Information) into logs
    ...(process.env.NODE_ENV !== 'production' && {
      log: ['query'],
    }),
  })

// Alias for backward compatibility — prefer `prisma` in new code
export const db = prisma

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = db
