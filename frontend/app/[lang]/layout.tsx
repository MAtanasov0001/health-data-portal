import type { Metadata } from "next";

import "@/app/globals.css";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";
import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";
import { SITE_URL } from "@/lib/site";

export function generateStaticParams() {
  return i18n.locales.map((lang) => ({ lang }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang: rawLang } = await params;
  const lang = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);
  return {
    metadataBase: new URL(SITE_URL),
    title: {
      default: dict.site.name,
      template: `%s · ${dict.site.short}`,
    },
    description: dict.home.lead,
    openGraph: {
      title: dict.site.name,
      description: dict.home.lead,
      siteName: dict.site.name,
      url: `/${lang}`,
      locale: lang,
      type: "website",
    },
  };
}

export default async function LangLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang: rawLang } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  return (
    <html lang={lang}>
      <body>
        <a className="skip-link" href="#main">
          {dict.nav.skip}
        </a>
        <SiteHeader lang={lang} dict={dict} />
        <main id="main" className="container">
          {children}
        </main>
        <SiteFooter lang={lang} dict={dict} />
      </body>
    </html>
  );
}
