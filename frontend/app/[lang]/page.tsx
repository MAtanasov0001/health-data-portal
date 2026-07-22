import Link from "next/link";

import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";

export default function HomePage({ params }: { params: { lang: string } }) {
  const lang: Locale = isLocale(params.lang) ? params.lang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "GovernmentService",
    name: dict.site.name,
    provider: { "@type": "GovernmentOrganization", name: dict.site.publisher },
    availableLanguage: i18n.locales,
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <section className="hero">
        <h1>{dict.home.title}</h1>
        <p className="lead">{dict.home.lead}</p>
        <p style={{ marginTop: "1.5rem" }}>
          <Link className="btn" href={`/${lang}/naborite`}>
            {dict.home.cta}
          </Link>
        </p>
      </section>

      <section aria-labelledby="principles">
        <h2 id="principles">{dict.home.principlesTitle}</h2>
        <ul>
          {dict.home.principles.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </section>
    </>
  );
}
