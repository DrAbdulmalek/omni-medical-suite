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

    // Hash default password — read from env so the literal never lives in source.
    // Operator MUST set SEED_ADMIN_PASSWORD before seeding; refuse to seed otherwise.
    const bcrypt = await import("bcryptjs");
    const seedPassword = process.env.SEED_ADMIN_PASSWORD;
    if (!seedPassword || seedPassword.length < 12) {
      return NextResponse.json(
        {
          success: false,
          error:
            "SEED_ADMIN_PASSWORD env var must be set to a value of at least 12 characters before seeding. Refusing to seed with a hardcoded default.",
        },
        { status: 400 }
      );
    }
    const hashedPassword = await bcrypt.hash(seedPassword, 12);

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
