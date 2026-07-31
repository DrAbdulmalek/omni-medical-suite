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

    // Hash default password
    const bcrypt = await import("bcryptjs");
    const hashedPassword = await bcrypt.hash("admin123", 12);

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
