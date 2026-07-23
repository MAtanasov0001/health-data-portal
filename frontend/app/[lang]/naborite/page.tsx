import type { Metadata } from "next";
import Link from "next/link";

import { i18n, isLocale, type Locale } from "@/i18n-config";
import {
  listCollections,
  listDatasets,
  localizedTitle,
  type CollectionList,
  type DatasetList,
} from "@/lib/api";
import { getDictionary } from "@/lib/dictionaries";

export const metadata: Metadata = { title: "Набори от данни" };

const nf = new Intl.NumberFormat("bg-BG");

export default async function DatasetsPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang: rawLang } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  let data: DatasetList = { total: 0, page: 1, page_size: 100, items: [] };
  let collections: CollectionList = { total: 0, items: [] };
  try {
    [data, collections] = await Promise.all([listDatasets(1, 100), listCollections()]);
  } catch {
    // API-то може да е недостъпно при статичен билд — показваме празно състояние.
  }

  // Членовете на колекция се показват вътре в колекцията, не в плоския списък.
  const standalone = data.items.filter((ds) => !ds.collection);

  return (
    <>
      <h1>{dict.datasets.title}</h1>
      <p className="lead">{dict.datasets.lead}</p>

      {collections.items.length > 0 && (
        <section aria-labelledby="collections-heading">
          <h2 id="collections-heading">{dict.datasets.collectionsTitle}</h2>
          <p className="section-lead">{dict.datasets.collectionsLead}</p>
          <ul className="card-grid">
            {collections.items.map((c) => (
              <li key={c.id} className="card card-collection">
                <span className="card-badge">{dict.datasets.collectionBadge}</span>
                <h3>
                  <Link href={`/${lang}/naborite/kolekciya/${c.id}`}>
                    {localizedTitle(c.title, lang)}
                  </Link>
                </h3>
                <p className="meta">
                  {c.table_count} {dict.datasets.tables} · {nf.format(c.total_rows)}{" "}
                  {dict.datasets.rows.toLowerCase()}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="standalone-heading">
        {collections.items.length > 0 && (
          <h2 id="standalone-heading">{dict.datasets.standaloneTitle}</h2>
        )}
        {standalone.length === 0 ? (
          <p>{dict.datasets.empty}</p>
        ) : (
          <ul className="card-grid">
            {standalone.map((ds) => (
              <li key={ds.identifier} className="card">
                <h3>
                  <Link href={`/${lang}/naborite/${ds.identifier}`}>
                    {localizedTitle(ds.title, lang)}
                  </Link>
                </h3>
                <p className="meta">
                  {dict.datasets.version}: {ds.version} · {dict.datasets.issued}: {ds.issued} ·{" "}
                  {dict.datasets.rows}: {nf.format(ds.row_count)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
