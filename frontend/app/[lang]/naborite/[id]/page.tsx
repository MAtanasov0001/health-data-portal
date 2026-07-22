import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { API_BASE, getDataset, localizedTitle } from "@/lib/api";
import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";

interface Params {
  lang: string;
  id: string;
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const lang: Locale = isLocale(params.lang) ? params.lang : i18n.defaultLocale;
  const ds = await getDataset(params.id);
  if (!ds) return { title: "404" };
  const title = localizedTitle(ds.title, lang);
  return {
    title,
    openGraph: { title, type: "article", locale: lang },
  };
}

export default async function DatasetDetailPage({ params }: { params: Params }) {
  const lang: Locale = isLocale(params.lang) ? params.lang : i18n.defaultLocale;
  const dict = getDictionary(lang);
  const ds = await getDataset(params.id);
  if (!ds) notFound();

  const title = localizedTitle(ds.title, lang);
  const disclosure = (ds.dcat["healthPortal:disclosureControl"] ?? {}) as Record<string, unknown>;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Dataset",
    name: title,
    identifier: ds.identifier,
    version: ds.version,
    dateModified: ds.issued,
    distribution: Object.entries(ds.distributions).map(([fmt, url]) => ({
      "@type": "DataDownload",
      encodingFormat: fmt.toUpperCase(),
      contentUrl: url,
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <p>
        <Link href={`/${lang}/naborite`}>← {dict.dataset.backToList}</Link>
      </p>
      <h1>{title}</h1>

      <h2>{dict.dataset.metadata}</h2>
      <dl className="kv">
        <dt>{dict.dataset.identifier}</dt>
        <dd>{ds.identifier}</dd>
        <dt>{dict.datasets.version}</dt>
        <dd>{ds.version}</dd>
        <dt>{dict.datasets.issued}</dt>
        <dd>{ds.issued}</dd>
        <dt>{dict.dataset.themes}</dt>
        <dd>{ds.themes.join(", ") || "—"}</dd>
        <dt>{dict.dataset.checksum}</dt>
        <dd>
          <code>{ds.checksum_sha256}</code>
        </dd>
        <dt>{dict.dataset.disclosure}</dt>
        <dd>
          {String(disclosure.method ?? "—")}
          {disclosure.minCellSize ? ` (min ${String(disclosure.minCellSize)})` : ""}
        </dd>
      </dl>

      <h2>{dict.dataset.downloads}</h2>
      <ul>
        {Object.entries(ds.distributions).map(([fmt, url]) => (
          <li key={fmt}>
            <a href={url}>{fmt.toUpperCase()}</a>
          </li>
        ))}
      </ul>

      <h2>{dict.dataset.apiTitle}</h2>
      <pre>
        <code>{`curl ${API_BASE}/v1/datasets/${ds.identifier}`}</code>
      </pre>
    </>
  );
}
