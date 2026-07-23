import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import CollectionExplorer from "@/components/CollectionExplorer";
import { API_BASE, getCollectionWithData, listCollections, localizedTitle } from "@/lib/api";
import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";
import { alternates } from "@/lib/site";

interface Params {
  lang: string;
  id: string;
}

const STATIC_EXPORT = process.env.STATIC_EXPORT === "1";

export async function generateStaticParams(): Promise<{ id: string }[]> {
  if (!STATIC_EXPORT) return [];
  try {
    const data = await listCollections();
    return data.items.map((c) => ({ id: c.id }));
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { lang: rawLang, id } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const loaded = await getCollectionWithData(id);
  if (!loaded) return { title: "404" };
  const title = localizedTitle(loaded.collection.title, lang);
  return {
    title,
    alternates: alternates(lang, `/naborite/kolekciya/${id}`),
    openGraph: { title, type: "website", locale: lang },
  };
}

export default async function CollectionPage({ params }: { params: Promise<Params> }) {
  const { lang: rawLang, id } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);
  const loaded = await getCollectionWithData(id);
  if (!loaded) notFound();

  const { collection, tables } = loaded;
  const title = localizedTitle(collection.title, lang);
  const description = localizedTitle(collection.description, lang);
  const labels = dict.columnLabels as Record<string, string>;
  const ex = dict.explorer as Record<string, string>;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "DataCatalog",
    name: title,
    description,
    dataset: collection.tables.map((t) => ({
      "@type": "Dataset",
      name: localizedTitle(t.title, lang),
      identifier: t.identifier,
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <nav className="breadcrumb" aria-label="breadcrumb">
        <Link href={`/${lang}/naborite`}>{dict.datasets.title}</Link>
        <span aria-hidden="true"> › </span>
        <span>{title}</span>
      </nav>

      <h1>{title}</h1>
      <p className="lead">{description}</p>
      <dl className="stat-strip">
        <div className="stat">
          <dt className="stat-label">{ex.tableCount}</dt>
          <dd className="stat-value">{collection.table_count}</dd>
        </div>
        <div className="stat">
          <dt className="stat-label">{ex.totalRows}</dt>
          <dd className="stat-value">{new Intl.NumberFormat("bg-BG").format(collection.total_rows)}</dd>
        </div>
        <div className="stat">
          <dt className="stat-label">{dict.datasets.issued}</dt>
          <dd className="stat-value">{collection.issued.slice(0, 10)}</dd>
        </div>
      </dl>

      <CollectionExplorer
        tables={tables}
        lang={lang}
        apiBase={API_BASE}
        labels={labels}
        strings={{
          chooseTable: ex.chooseTable,
          dimension: ex.dimension,
          measure: ex.measure,
          chartType: ex.chartType,
          bar: ex.bar,
          pie: ex.pie,
          none: ex.none,
          topN: ex.topN,
          filter: ex.filter,
          filterPlaceholder: ex.filterPlaceholder,
          rows: ex.rows,
          showingTop: ex.showingTop,
          download: ex.download,
          apiHint: ex.apiHint,
          tableTab: ex.tableTab,
          chartTab: ex.chartTab,
          chartEmpty: ex.chartEmpty,
          noResults: ex.noResults,
        }}
      />
    </>
  );
}
