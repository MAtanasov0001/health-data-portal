"use client";

import Link from "next/link";
import { useId, useMemo, useState } from "react";

import type { CollectionSummary, DatasetSummary } from "@/lib/api";
import { localizedTitle } from "@/lib/api";
import { numberFormat } from "@/lib/format";

interface SearchStrings {
  searchLabel: string;
  searchPlaceholder: string;
  themeAll: string;
  resultsOne: string;
  resultsMany: string;
  noResults: string;
  collectionsTitle: string;
  collectionsLead: string;
  collectionBadge: string;
  standaloneTitle: string;
  tables: string;
  rows: string;
  version: string;
  issued: string;
  empty: string;
}

interface Props {
  datasets: DatasetSummary[];
  collections: CollectionSummary[];
  lang: string;
  strings: SearchStrings;
  themeLabels: Record<string, string>;
}

function themeLabel(code: string, labels: Record<string, string>): string {
  return labels[code] ?? code;
}

export default function DatasetSearch({ datasets, collections, lang, strings, themeLabels }: Props) {
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState("");
  const nf = numberFormat(lang);
  const searchId = useId();

  // Всички теми, срещащи се в наборите и колекциите — за фасетата.
  const themes = useMemo(() => {
    const seen = new Set<string>();
    for (const d of datasets) for (const t of d.themes) seen.add(t);
    for (const c of collections) for (const t of c.themes) seen.add(t);
    return [...seen].sort();
  }, [datasets, collections]);

  const needle = query.trim().toLowerCase();

  const matchesText = (title: Record<string, string>, id: string): boolean => {
    if (!needle) return true;
    const hay = [id, ...Object.values(title)].join(" ").toLowerCase();
    return hay.includes(needle);
  };
  const matchesTheme = (list: string[]): boolean => !theme || list.includes(theme);

  const shownCollections = collections.filter(
    (c) => matchesText(c.title, c.id) && matchesTheme(c.themes),
  );
  const shownDatasets = datasets.filter(
    (d) => matchesText(d.title, d.identifier) && matchesTheme(d.themes),
  );

  const count = shownCollections.length + shownDatasets.length;
  const resultText = count === 1 ? strings.resultsOne : `${count} ${strings.resultsMany}`;

  return (
    <>
      <form className="dataset-search" role="search" onSubmit={(e) => e.preventDefault()}>
        <div className="dataset-search-field">
          <label htmlFor={searchId}>{strings.searchLabel}</label>
          <input
            id={searchId}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={strings.searchPlaceholder}
            autoComplete="off"
          />
        </div>
        {themes.length > 0 && (
          <div className="dataset-search-facets" role="group" aria-label={strings.themeAll}>
            <button
              type="button"
              className={`facet-chip${theme === "" ? " is-active" : ""}`}
              aria-pressed={theme === ""}
              onClick={() => setTheme("")}
            >
              {strings.themeAll}
            </button>
            {themes.map((t) => (
              <button
                key={t}
                type="button"
                className={`facet-chip${theme === t ? " is-active" : ""}`}
                aria-pressed={theme === t}
                onClick={() => setTheme(theme === t ? "" : t)}
              >
                {themeLabel(t, themeLabels)}
              </button>
            ))}
          </div>
        )}
        <p className="dataset-search-count" role="status" aria-live="polite">
          {resultText}
        </p>
      </form>

      {count === 0 ? (
        <p>{strings.noResults}</p>
      ) : (
        <>
          {shownCollections.length > 0 && (
            <section aria-labelledby="collections-heading">
              <h2 id="collections-heading">{strings.collectionsTitle}</h2>
              <p className="section-lead">{strings.collectionsLead}</p>
              <ul className="card-grid">
                {shownCollections.map((c) => (
                  <li key={c.id} className="card card-collection">
                    <span className="card-badge">{strings.collectionBadge}</span>
                    <h3>
                      <Link href={`/${lang}/naborite/kolekciya/${c.id}`}>
                        {localizedTitle(c.title, lang)}
                      </Link>
                    </h3>
                    <p className="meta">
                      {c.table_count} {strings.tables} · {nf.format(c.total_rows)}{" "}
                      {strings.rows.toLowerCase()}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {shownDatasets.length > 0 && (
            <section aria-labelledby="standalone-heading">
              <h2 id="standalone-heading">{strings.standaloneTitle}</h2>
              <ul className="card-grid">
                {shownDatasets.map((ds) => (
                  <li key={ds.identifier} className="card">
                    <h3>
                      <Link href={`/${lang}/naborite/${ds.identifier}`}>
                        {localizedTitle(ds.title, lang)}
                      </Link>
                    </h3>
                    <p className="meta">
                      {strings.version}: {ds.version} · {strings.issued}: {ds.issued} ·{" "}
                      {strings.rows}: {nf.format(ds.row_count)}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </>
  );
}
