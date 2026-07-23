import type { Metadata } from "next";
import Link from "next/link";

import { API_BASE, CKAN_BASE } from "@/lib/api";
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
  return { title: getDictionary(lang).docs.title, alternates: alternates(lang, "/dokumentacia") };
}

export default async function DocsPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang: rawLang } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  return (
    <>
      <p className="breadcrumb">
        <Link href={`/${lang}`}>{dict.nav.home}</Link> / {dict.docs.title}
      </p>
      <h1>{dict.docs.title}</h1>
      <p className="lead">{dict.docs.lead}</p>

      <section aria-labelledby="api-heading">
        <h2 id="api-heading">{dict.docs.apiTitle}</h2>
        <p className="section-lead">{dict.docs.apiLead}</p>
        <ul className="link-list">
          <li>
            <a href={`${API_BASE}/docs`}>{dict.docs.swagger}</a>
          </li>
          <li>
            <a href={`${API_BASE}/openapi.json`}>{dict.docs.openapi}</a>
          </li>
          <li>
            <a href={`${API_BASE}/v1/catalog.jsonld`}>{dict.docs.dcatCatalog}</a>
          </li>
        </ul>
      </section>

      <section aria-labelledby="formats-heading">
        <h2 id="formats-heading">{dict.docs.formatsTitle}</h2>
        <ul className="checklist">
          {dict.docs.formats.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="catalog-heading">
        <h2 id="catalog-heading">{dict.docs.catalogTitle}</h2>
        <p className="section-lead">{dict.docs.catalogBody}</p>
        <ul className="link-list">
          <li>
            <a href={`${CKAN_BASE}/catalog.jsonld`}>{dict.docs.ckanJsonld}</a>
          </li>
          <li>
            <a href={`${CKAN_BASE}/catalog.xml`}>{dict.docs.ckanXml}</a>
          </li>
          <li>
            <a href={`${CKAN_BASE}/api/3/action/package_list`}>{dict.docs.ckanPackages}</a>
          </li>
        </ul>
      </section>

      <section aria-labelledby="examples-heading">
        <h2 id="examples-heading">{dict.docs.examplesTitle}</h2>
        <pre>
          <code>{`# ${dict.datasets.title} (${lang === "bg" ? "пагиниран" : "paginated"})
curl "${API_BASE}/v1/datasets?page=1&page_size=20"

# ${dict.dataset.metadata}
curl "${API_BASE}/v1/datasets/hospitalizacii-po-oblast-2023"

# CSV / JSON
curl "${API_BASE}/v1/datasets/hospitalizacii-po-oblast-2023/data.csv"
curl "${API_BASE}/v1/datasets/hospitalizacii-po-oblast-2023/data.json"

# CKAN ${lang === "bg" ? "харвестване" : "harvesting"}
curl "${API_BASE}/api/3/action/package_list"`}</code>
        </pre>
      </section>
    </>
  );
}
