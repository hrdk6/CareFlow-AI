import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// UX-level gate only: send visitors without a session cookie to /login.
// Real authentication and authorization happen in the FastAPI backend on every API call.
export function proxy(request: NextRequest) {
  const hasSession = request.cookies.has("careflow_session");
  const isLogin = request.nextUrl.pathname === "/login";
  if (!hasSession && !isLogin) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
  // A cookie can outlive its session (secret rotated, account deactivated). The app then sends the browser to
  // /login?next=..., which must render the form instead of bouncing back to "/" and looping.
  if (hasSession && isLogin && !request.nextUrl.searchParams.has("next")) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // Pages only: API calls, Next internals and files with an extension (icons, images) pass straight through.
  matcher: ["/((?!api|_next/static|_next/image|.*\\..*).*)"],
};
