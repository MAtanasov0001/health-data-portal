import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import BarChart from "@/components/BarChart";
import {
  API_BASE,
  getDataset,
  getDatasetRows,
  getSummary,
  listDatasets,
  localizedTitle,
} from "@/lib/api";
import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";
import { alternates } from "@/lib/site";

interface Params {
  lang: string;
  id: string;
}

const PAGE_SIZE = 20;

// Статичен експорт (демо/staging): без сървър, затова четенето на searchParams се пропуска и
// генерираме идентификаторите предварително. При SSR (продукция) нищо от това не се активира.
const STATIC_EXPORT = process.env.STATIC_EXPORT === "1";

export async function generateStaticParams(): Promise<{ id: string }[]> {
  if (!STATIC_EXPORT) return [];
  try {
    const data = await listDatasets(1, 100);
    return data.items.map((d) => ({ id: d.identifier }));
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
  const ds = await getDataset(id);
  if (!ds) return { title: "404" };
  const title = localizedTitle(ds.title, lang);
  return {
    title,
    alternates: alternates(lang, `/naborite/${id}`),
    openGraph: { title, type: "article", locale: lang },
  };
}

export default async function DatasetDetailPage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<{ page?: string }>;
}) {
  const { lang: rawLang, id } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);
  const ds = await getDataset(id);
  if (!ds) notFound();

  const sp = STATIC_EXPORT ? {} : await searchParams;
  const page = Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1);
  const [rowsPage, summary] = await Promise.all([
    getDatasetRows(id, page, PAGE_SIZE),
    getSummary(id, 10),
  ]);

  const colLabels = dict.columnLabels as Record<string, string>;
  const label = (col: string): string => colLabels[col] ?? col;

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

      {summary && summary.groups.length > 0 && (
        <section aria-labelledby="chart-heading">
          <h2 id="chart-heading">{dict.dataset.chartTitle}</h2>
          <p className="meta">
            {dict.dataset.chartTop}: {label(summary.dimension)} · {label(summary.measure)}
          </p>
          <BarChart
            groups={summary.groups}
            title={`${label(summary.measure)} — ${label(summary.dimension)}`}
            valueLabel={label(summary.measure)}
            keyLabel={label(summary.dimension)}
            lang={lang}
          />
        </section>
      )}

      {rowsPage && rowsPage.rows.length > 0 && (
        <section aria-labelledby="preview-heading">
          <h2 id="preview-heading">{dict.dataset.preview}</h2>
          <div className="table-scroll" tabIndex={0} role="region" aria-label={dict.dataset.preview}>
            <table className="data">
              <thead>
                <tr>
                  {Object.keys(rowsPage.rows[0]).map((col) => (
                    <th key={col} scope="col">
                      {label(col)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rowsPage.rows.map((row, i) => (
                  <tr key={i}>
                    {Object.keys(rowsPage.rows[0]).map((col) => (
                      <td key={col}>{row[col] ?? "—"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav className="pager" aria-label={dict.dataset.pagination}>
            {page > 1 ? (
              <Link rel="prev" href={`?page=${page - 1}`}>
                ← {dict.dataset.prev}
              </Link>
            ) : (
              <span aria-disabled="true">← {dict.dataset.prev}</span>
            )}
            <span className="meta">
              {dict.dataset.page} {page} / {Math.max(1, Math.ceil(rowsPage.total / PAGE_SIZE))} ·{" "}
              {rowsPage.total} {dict.datasets.rows.toLowerCase()}
            </span>
            {page < Math.ceil(rowsPage.total / PAGE_SIZE) ? (
              <Link rel="next" href={`?page=${page + 1}`}>
                {dict.dataset.next} →
              </Link>
            ) : (
              <span aria-disabled="true">{dict.dataset.next} →</span>
            )}
          </nav>
        </section>
      )}

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
