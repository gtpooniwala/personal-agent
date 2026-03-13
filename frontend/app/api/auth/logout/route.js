import { cookies, headers } from "next/headers";
import { NextResponse } from "next/server";

export async function POST(request) {
  const headerList = await headers();
  const origin = headerList.get("origin");
  const host = headerList.get("host");

  if (origin) {
    const originUrl = new URL(origin);
    if (originUrl.host !== host) {
      return NextResponse.json({ detail: "Invalid origin" }, { status: 403 });
    }
  }

  const cookieStore = await cookies();
  cookieStore.delete("pa_session");
  
  return NextResponse.redirect(new URL("/login", request.url), { status: 303 });
}

