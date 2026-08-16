import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Must match backend/app/core/config.py Settings.session_cookie_name.
const SESSION_COOKIE_NAME = "finanz_agent_session";
const PUBLIC_PATHS = ["/login"];

// This is an optimistic check only (cookie presence, not validity) — the real auth check
// happens per-request on the backend via get_current_user. See Next.js's own guidance on
// not relying on Proxy as a full session management/authorization solution.
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSessionCookie = request.cookies.has(SESSION_COOKIE_NAME);
  const isPublicPath = PUBLIC_PATHS.includes(pathname);

  if (!hasSessionCookie && !isPublicPath) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (hasSessionCookie && isPublicPath) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
