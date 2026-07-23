import type { Metadata } from "next";
import Link from "next/link";

import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";

export const metadata: Metadata = { title: "За портала" };

export default async function AboutPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang: rawLang } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  return (
    <>
      <p className="breadcrumb">
        <Link href={`/${lang}`}>{dict.nav.home}</Link> / {dict.about.title}
      </p>
      <h1>{dict.about.title}</h1>
      <p className="lead">{dict.about.lead}</p>

      <section aria-labelledby="origin-heading" className="prose">
        <h2 id="origin-heading">{dict.about.originTitle}</h2>
        {dict.about.origin.map((p) => (
          <p key={p}>{p}</p>
        ))}
      </section>

      <section aria-labelledby="governance-heading">
        <h2 id="governance-heading">{dict.about.governanceTitle}</h2>
        <ul className="checklist">
          {dict.about.governance.map((g) => (
            <li key={g}>{g}</li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="standards-heading">
        <h2 id="standards-heading">{dict.about.standardsTitle}</h2>
        <ul className="checklist">
          {dict.about.standards.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </section>

      <p className="cta-row">
        <Link className="btn" href={`/${lang}/naborite`}>
          {dict.home.cta}
        </Link>
        <Link className="btn-ghost" href={`/${lang}/dokumentacia`}>
          {dict.home.ctaDocs}
        </Link>
      </p>
    </>
  );
}
