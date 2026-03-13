import { NextResponse } from "next/server";
import { verifySession } from "@/lib/session";

export async function middleware(request) {
  // If in development mode and AUTH_USERS is not set, bypass authentication
  if (process.env.NODE_ENV === "development" && !process.env.AUTH_USERS && process.env.ALLOW_EMPTY_AUTH === "true") {
    return NextResponse.next();
  }

  // Paths that don't require authentication
  const publicPaths = ["/login", "/api/auth/logout"];
  const { pathname } = request.nextUrl;
  
  if (publicPaths.some(p => pathname.startsWith(p) || pathname === p)) {
    return NextResponse.next();
  }

  // Check for session cookie
  const sessionToken = request.cookies.get("pa_session")?.value;
  const session = await verifySession(sessionToken);

  if (!session) {
    // If it's an API route, return 401
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
    }
    
    // Otherwise, redirect to login page
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  // Set X-Frontend-User for backend tracking
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("X-Frontend-User", session.username);

  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

export const config = {
  // Run on all routes except static files
  matcher: ["/((?!_next/static|_next/image|favicon.ico|favicon.svg).*)"],
};
