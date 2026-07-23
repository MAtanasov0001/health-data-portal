import type { Metadata } from "next";

import DatasetSearch from "@/components/DatasetSearch";
import { i18n, isLocale, type Locale } from "@/i18n-config";
import { listCollections, listDatasets, type CollectionList, type DatasetList } from "@/lib/api";
import { getDictionary } from "@/lib/dictionaries";
import { alternates } from "@/lib/site";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang: rawLang } = await params;
  const lang = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  return { title: getDictionary(lang).datasets.title, alternates: alternates(lang, "/naborite") };
}

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
  const themeLabels = dict.themeLabels as Record<string, string>;
  const d = dict.datasets;

  return (
    <>
      <h1>{d.title}</h1>
      <p className="lead">{d.lead}</p>

      {standalone.length === 0 && collections.items.length === 0 ? (
        <p>{d.empty}</p>
      ) : (
        <DatasetSearch
          datasets={standalone}
          collections={collections.items}
          lang={lang}
          themeLabels={themeLabels}
          strings={{
            searchLabel: d.searchLabel,
            searchPlaceholder: d.searchPlaceholder,
            themeAll: d.themeAll,
            resultsOne: d.resultsOne,
            resultsMany: d.resultsMany,
            noResults: d.noResults,
            collectionsTitle: d.collectionsTitle,
            collectionsLead: d.collectionsLead,
            collectionBadge: d.collectionBadge,
            standaloneTitle: d.standaloneTitle,
            tables: d.tables,
            rows: d.rows,
            version: d.version,
            issued: d.issued,
            empty: d.empty,
          }}
        />
      )}
    </>
  );
}
