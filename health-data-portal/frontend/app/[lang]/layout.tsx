import type { Metadata } from "next";

import "@/app/globals.css";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";
import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";

export function generateStaticParams() {
  return i18n.locales.map((lang) => ({ lang }));
}

export async function generateMetadata({
  params,
}: {
  params: { lang: string };
}): Promise<Metadata> {
  const lang = isLocale(params.lang) ? params.lang : i18n.defaultLocale;
  const dict = getDictionary(lang);
  return {
    title: {
      default: dict.site.name,
      template: `%s · ${dict.site.short}`,
    },
    description: dict.home.lead,
    openGraph: {
      title: dict.site.name,
      description: dict.home.lead,
      locale: lang,
      type: "website",
    },
  };
}

export default function LangLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { lang: string };
}) {
  const lang: Locale = isLocale(params.lang) ? params.lang : i18n.defaultLocale;
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
        <SiteFooter dict={dict} />
      </body>
    </html>
  );
}
