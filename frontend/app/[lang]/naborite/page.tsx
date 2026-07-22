import type { Metadata } from "next";
import Link from "next/link";

import { i18n, isLocale, type Locale } from "@/i18n-config";
import { listDatasets, localizedTitle, type DatasetList } from "@/lib/api";
import { getDictionary } from "@/lib/dictionaries";

export const metadata: Metadata = { title: "Набори от данни" };

export default async function DatasetsPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang: rawLang } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  let data: DatasetList = { total: 0, page: 1, page_size: 20, items: [] };
  try {
    data = await listDatasets();
  } catch {
    // API-то може да е недостъпно при статичен билд — показваме празно състояние.
  }

  return (
    <>
      <h1>{dict.datasets.title}</h1>
      <p className="lead">{dict.datasets.lead}</p>

      {data.items.length === 0 ? (
        <p>{dict.datasets.empty}</p>
      ) : (
        <ul className="card-grid">
          {data.items.map((ds) => (
            <li key={ds.identifier} className="card">
              <h3>
                <Link href={`/${lang}/naborite/${ds.identifier}`}>
                  {localizedTitle(ds.title, lang)}
                </Link>
              </h3>
              <p className="meta">
                {dict.datasets.version}: {ds.version} · {dict.datasets.issued}: {ds.issued} ·{" "}
                {dict.datasets.rows}: {ds.row_count}
              </p>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
