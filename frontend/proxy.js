import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((request) => {
  // Local dev bypass: skip auth when allowed emails are not configured
  if (
    process.env.NODE_ENV === "development" &&
    !process.env.AUTH_ALLOWED_EMAILS &&
    process.env.ALLOW_EMPTY_AUTH === "true"
  ) {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;

  // NextAuth's own routes and the login page are always public
  if (pathname === "/login" || pathname.startsWith("/api/auth/")) {
    return NextResponse.next();
  }

  if (!request.auth) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
    }
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const email = request.auth.user?.email;
  if (!email) {
    return NextResponse.next();
  }

  // Forward the authenticated user's email to the backend for tracking
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("X-Frontend-User", email);

  return NextResponse.next({
    request: { headers: requestHeaders },
  });
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|favicon.svg).*)"],
};
