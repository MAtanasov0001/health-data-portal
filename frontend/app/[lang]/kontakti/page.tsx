import type { Metadata } from "next";
import Link from "next/link";

import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";
import { alternates } from "@/lib/site";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang: rawLang } = await params;
  const lang = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  return { title: getDictionary(lang).contact.title, alternates: alternates(lang, "/kontakti") };
}

export default async function ContactPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang: rawLang } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  return (
    <>
      <p className="breadcrumb">
        <Link href={`/${lang}`}>{dict.nav.home}</Link> / {dict.contact.title}
      </p>
      <h1>{dict.contact.title}</h1>
      <p className="lead">{dict.contact.lead}</p>

      <div className="card-grid">
        <section className="panel" aria-labelledby="email-heading">
          <h2 id="email-heading">{dict.contact.emailTitle}</h2>
          <p>
            <a href="mailto:data@health.egov.bg">data@health.egov.bg</a>
          </p>
        </section>

        <section className="panel" aria-labelledby="repo-heading">
          <h2 id="repo-heading">{dict.contact.repoTitle}</h2>
          <p>{dict.contact.repoBody}</p>
          <p>
            <a href="https://git.egov.bg" rel="noopener">
              {dict.contact.repoLink} →
            </a>
          </p>
        </section>

        <section className="panel" aria-labelledby="security-heading">
          <h2 id="security-heading">{dict.contact.securityTitle}</h2>
          <p role="note">{dict.contact.security}</p>
        </section>
      </div>
    </>
  );
}
