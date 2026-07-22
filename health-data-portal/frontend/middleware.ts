import { NextRequest, NextResponse } from "next/server";

import { i18n } from "./i18n-config";

// Пренасочва пътища без локал към локал по подразбиране (/ → /bg), за да има всеки ресурс
// уникален адрес с език (МЕ72; SSR за SEO с коректен lang атрибут).
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const hasLocale = i18n.locales.some(
    (loc) => pathname === `/${loc}` || pathname.startsWith(`/${loc}/`),
  );
  if (hasLocale) return;

  const locale = i18n.defaultLocale;
  const url = request.nextUrl.clone();
  url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next|api|.*\\..*).*)"],
};
