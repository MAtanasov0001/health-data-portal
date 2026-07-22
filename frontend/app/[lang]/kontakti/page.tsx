import type { Metadata } from "next";

import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";

export const metadata: Metadata = { title: "Контакти" };

export default function ContactPage({ params }: { params: { lang: string } }) {
  const lang: Locale = isLocale(params.lang) ? params.lang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  return (
    <>
      <h1>{dict.contact.title}</h1>
      <p className="lead">{dict.contact.lead}</p>

      <address>
        <a href="mailto:data@health.egov.bg">data@health.egov.bg</a>
      </address>

      <p role="note">{dict.contact.security}</p>
    </>
  );
}
