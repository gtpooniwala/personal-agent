import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function POST(request) {
  const cookieStore = await cookies();
  cookieStore.delete("pa_session");
  
  return NextResponse.redirect(new URL("/login", request.url), { status: 302 });
}

