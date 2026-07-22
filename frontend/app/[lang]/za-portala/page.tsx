import type { Metadata } from "next";

import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";

export const metadata: Metadata = { title: "За портала" };

export default async function AboutPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang: rawLang } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  return (
    <>
      <h1>{dict.about.title}</h1>
      <p className="lead">{dict.about.lead}</p>

      <ul>
        {dict.home.principles.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
    </>
  );
}
