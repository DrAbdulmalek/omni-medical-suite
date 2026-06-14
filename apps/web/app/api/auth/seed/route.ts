/**
 * Seed API Route - Creates default admin user
 * Run once on fresh setup: GET /api/auth/seed
 */

import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET() {
  try {
    // Check if admin already exists
    const existing = await prisma.user.findUnique({
      where: { username: "admin" },
    });

    if (existing) {
      return NextResponse.json({
        success: false,
        message: "Admin user already exists. Skipping seed.",
        username: existing.username,
        role: existing.role,
      });
    }

    // Hash admin password from environment variable
    const bcrypt = await import("bcryptjs");
    const adminPassword = process.env.ADMIN_SEED_PASSWORD;
    if (!adminPassword) {
      throw new Error(
        "ADMIN_SEED_PASSWORD environment variable is required for seeding. " +
        "Generate one with: node -e \"console.log(require('crypto').randomBytes(32).toString('hex'))\""
      );
    }
    const hashedPassword = await bcrypt.hash(adminPassword, 12);

    const admin = await prisma.user.create({
      data: {
        username: "admin",
        password: hashedPassword,
        role: "admin",
      },
    });

    return NextResponse.json({
      success: true,
      message: "Default admin user created. CHANGE PASSWORD IMMEDIATELY!",
      username: admin.username,
      role: admin.role,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
