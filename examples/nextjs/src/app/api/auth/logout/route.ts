import { NextResponse } from "next/server";

import { clearSession } from "@/lib/auth";

export async function POST(): Promise<NextResponse> {
  await clearSession();
  return NextResponse.redirect(new URL("/", "http://127.0.0.1:3000"));
}
