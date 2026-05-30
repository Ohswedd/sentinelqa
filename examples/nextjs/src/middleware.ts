import { NextRequest, NextResponse } from "next/server";

const PROTECTED_PREFIXES = ["/projects", "/dashboard", "/admin"];

export function middleware(request: NextRequest): NextResponse {
  const path = request.nextUrl.pathname;
  const protectedPath = PROTECTED_PREFIXES.some(
    (prefix) => path === prefix || path.startsWith(`${prefix}/`),
  );
  if (!protectedPath) return NextResponse.next();
  const session = request.cookies.get("sentinel_demo_session");
  if (!session) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", path);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/projects/:path*", "/dashboard/:path*", "/admin/:path*"],
};
