import Link from "next/link";

import BarChart from "@/components/BarChart";
import { getSummary, listDatasets, localizedTitle } from "@/lib/api";
import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";

// Пилотни набори, използвани за началните визуализации (сумата на реимбурса и броя случаи).
const CHART_MONEY_ID = "deynosti-lekarstva-nzok-2025";
const CHART_CASES_ID = "deynosti-kp-nzok-2025";

export default async function HomePage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang: rawLang } = await params;
  const lang: Locale = isLocale(rawLang) ? rawLang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  const [list, moneySummary, casesSummary] = await Promise.all([
    listDatasets(1, 20).catch(() => null),
    getSummary(CHART_MONEY_ID, 6),
    getSummary(CHART_CASES_ID, 6),
  ]);

  const items = list?.items ?? [];
  const totalDatasets = list?.total ?? items.length;
  const totalRecords = items.reduce((sum, d) => sum + (d.row_count ?? 0), 0);
  const themeCount = new Set(items.flatMap((d) => d.themes)).size;
  const lastUpdated = items
    .map((d) => d.issued)
    .sort()
    .at(-1);

  const nf = new Intl.NumberFormat(lang === "bg" ? "bg-BG" : "en-GB");
  const fmtDate = (iso?: string): string =>
    iso
      ? new Intl.DateTimeFormat(lang === "bg" ? "bg-BG" : "en-GB", {
          year: "numeric",
          month: "short",
          day: "numeric",
        }).format(new Date(iso))
      : "—";

  const featured = items.slice(0, 6);

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
        <p className="eyebrow">{dict.home.eyebrow}</p>
        <h1>{dict.home.title}</h1>
        <p className="lead">{dict.home.lead}</p>
        <div className="cta-row">
          <Link className="btn" href={`/${lang}/naborite`}>
            {dict.home.cta}
          </Link>
          <Link className="btn-ghost" href={`/${lang}/dokumentacia`}>
            {dict.home.ctaDocs}
          </Link>
        </div>
        <dl className="stat-strip">
          <div className="stat">
            <dt className="stat-label">{dict.home.stats.datasets}</dt>
            <dd className="stat-value">{nf.format(totalDatasets)}</dd>
          </div>
          <div className="stat">
            <dt className="stat-label">{dict.home.stats.records}</dt>
            <dd className="stat-value">{nf.format(totalRecords)}</dd>
          </div>
          <div className="stat">
            <dt className="stat-label">{dict.home.stats.themes}</dt>
            <dd className="stat-value">{nf.format(themeCount)}</dd>
          </div>
          <div className="stat">
            <dt className="stat-label">{dict.home.stats.updated}</dt>
            <dd className="stat-value">{fmtDate(lastUpdated)}</dd>
          </div>
        </dl>
      </section>

      {featured.length > 0 && (
        <section aria-labelledby="explore-heading">
          <div className="section-head">
            <h2 id="explore-heading">{dict.home.exploreTitle}</h2>
            <Link className="section-link" href={`/${lang}/naborite`}>
              {dict.home.viewAll} →
            </Link>
          </div>
          <p className="section-lead">{dict.home.exploreLead}</p>
          <ul className="card-grid">
            {featured.map((d) => (
              <li className="card" key={d.identifier}>
                <h3>
                  <Link href={`/${lang}/naborite/${d.identifier}`}>
                    {localizedTitle(d.title, lang)}
                  </Link>
                </h3>
                <p className="meta">
                  {dict.datasets.version} {d.version} · {nf.format(d.row_count)}{" "}
                  {dict.datasets.rows.toLowerCase()} · {fmtDate(d.issued)}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {(moneySummary?.groups.length || casesSummary?.groups.length) && (
        <section aria-labelledby="charts-heading">
          <h2 id="charts-heading">{dict.home.chartsTitle}</h2>
          <p className="section-lead">{dict.home.chartsLead}</p>
          <div className="chart-grid">
            {moneySummary && moneySummary.groups.length > 0 && (
              <BarChart
                groups={moneySummary.groups}
                title={dict.home.chartsMoney}
                valueLabel={lang === "bg" ? "лв." : "BGN"}
              />
            )}
            {casesSummary && casesSummary.groups.length > 0 && (
              <BarChart
                groups={casesSummary.groups}
                title={dict.home.chartsCases}
                valueLabel={lang === "bg" ? "случаи" : "cases"}
              />
            )}
          </div>
        </section>
      )}

      <section aria-labelledby="pipeline-heading">
        <h2 id="pipeline-heading">{dict.home.pipelineTitle}</h2>
        <ol className="pipeline">
          {dict.home.pipeline.map((step, i) => (
            <li className="pipeline-step" key={step.title}>
              <span className="pipeline-num" aria-hidden="true">
                {i + 1}
              </span>
              <div>
                <h3>{step.title}</h3>
                <p className="meta">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="mission-heading" className="mission">
        <h2 id="mission-heading">{dict.home.missionTitle}</h2>
        {dict.home.mission.map((p) => (
          <p className="mission-p" key={p}>
            {p}
          </p>
        ))}
        <h3 className="mission-sub">{dict.home.principlesTitle}</h3>
        <ul className="principles">
          {dict.home.principles.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </section>
    </>
  );
}
