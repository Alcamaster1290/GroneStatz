import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const SESSION_COOKIE_KEY = "fantasy_session";

const PUBLIC_ONLY_PATHS = new Set(["/landing", "/login"]);
const PRIVATE_PREFIXES = ["/app", "/team", "/market", "/stats", "/settings", "/transfer"];

const normalizePathname = (pathname: string) => {
  if (!pathname || pathname === "/") return "/";
  return pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
};

const isPrivatePath = (pathname: string) =>
  PRIVATE_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));

export function middleware(request: NextRequest) {
  const pathname = normalizePathname(request.nextUrl.pathname);
  const hasSession = request.cookies.get(SESSION_COOKIE_KEY)?.value === "1";

  if (hasSession && PUBLIC_ONLY_PATHS.has(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/app";
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (!hasSession && isPrivatePath(pathname)) {
    const url = request.nextUrl.clone();
    const redirectTo = `${request.nextUrl.pathname}${request.nextUrl.search || ""}`;
    url.pathname = "/login";
    url.search = "";
    url.searchParams.set("redirect", redirectTo);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|favicon.png|apple-touch-icon.png|manifest.json|robots.txt|sitemap.xml|icons|images|sw.js).*)"
  ]
};
