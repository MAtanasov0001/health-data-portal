"use client";

import { useMemo, useState } from "react";

import type { TableData } from "@/lib/api";
import { numberFormat } from "@/lib/format";

type ChartType = "bar" | "pie" | "none";

interface ExplorerStrings {
  chooseTable: string;
  dimension: string;
  measure: string;
  chartType: string;
  bar: string;
  pie: string;
  none: string;
  topN: string;
  filter: string;
  filterPlaceholder: string;
  rows: string;
  showingTop: string;
  download: string;
  apiHint: string;
  tableTab: string;
  chartTab: string;
  chartEmpty: string;
  noResults: string;
}

interface Props {
  tables: TableData[];
  lang: string;
  apiBase: string;
  labels: Record<string, string>;
  strings: ExplorerStrings;
}

const PALETTE = [
  "#00664d",
  "#138d62",
  "#3aa981",
  "#6cc3a3",
  "#9bd8c1",
  "#f0a500",
  "#d0201f",
  "#4f5b57",
  "#005842",
  "#8bbf9f",
];

function toNumber(raw: string | null): number | null {
  if (raw == null || raw === "") return null;
  const v = Number(String(raw).replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(v) ? v : null;
}

function aggregate(
  rows: Record<string, string | null>[],
  dim: string,
  measure: string,
  topN: number,
): { key: string; value: number }[] {
  const sums = new Map<string, number>();
  for (const row of rows) {
    const value = toNumber(row[measure]);
    if (value === null) continue;
    const key = row[dim] ?? "—";
    sums.set(key, (sums.get(key) ?? 0) + value);
  }
  return [...sums.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, topN)
    .map(([key, value]) => ({ key, value }));
}

function polar(cx: number, cy: number, r: number, angle: number): [number, number] {
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

function label(labels: Record<string, string>, col: string): string {
  return labels[col] ?? col;
}

export default function CollectionExplorer({ tables, lang, apiBase, labels, strings }: Props) {
  const [selected, setSelected] = useState(0);
  const table = tables[selected];

  const [dimension, setDimension] = useState(table?.dimensions[0] ?? "");
  const [measure, setMeasure] = useState(table?.measures[0] ?? "");
  const [chartType, setChartType] = useState<ChartType>("bar");
  const [topN, setTopN] = useState(10);
  const [filter, setFilter] = useState("");
  const [view, setView] = useState<"chart" | "table">("chart");

  const nf = numberFormat(lang);

  function selectTable(i: number) {
    const t = tables[i];
    setSelected(i);
    setDimension(t.dimensions[0] ?? "");
    setMeasure(t.measures[0] ?? "");
    setFilter("");
  }

  const groups = useMemo(() => {
    if (!table || !dimension || !measure) return [];
    return aggregate(table.rows, dimension, measure, topN);
  }, [table, dimension, measure, topN]);

  const filteredRows = useMemo(() => {
    if (!table) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return table.rows;
    return table.rows.filter((row) =>
      Object.values(row).some((v) => (v ?? "").toLowerCase().includes(q)),
    );
  }, [table, filter]);

  if (!table) return null;

  const max = groups.length ? Math.max(...groups.map((g) => g.value)) : 0;
  const total = groups.reduce((s, g) => s + g.value, 0);
  const titleText = table.title[lang] ?? table.title.bg ?? table.identifier;

  return (
    <div className="explorer">
      <nav className="explorer-tree" aria-label={strings.chooseTable}>
        <p className="explorer-tree-head">{strings.chooseTable}</p>
        <ul>
          {tables.map((t, i) => (
            <li key={t.identifier}>
              <button
                type="button"
                className={i === selected ? "is-active" : ""}
                aria-current={i === selected ? "true" : undefined}
                onClick={() => selectTable(i)}
              >
                <span className="explorer-tree-title">
                  {t.title[lang] ?? t.title.bg ?? t.identifier}
                </span>
                <span className="explorer-tree-meta">
                  {t.rows.length} {strings.rows}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="explorer-panel">
        <h3 className="explorer-title">{titleText}</h3>
        <p className="meta">
          {table.rows.length} {strings.rows} · {strings.dimension}: {table.dimensions.map((d) => label(labels, d)).join(", ")} ·{" "}
          {strings.measure}: {table.measures.map((m) => label(labels, m)).join(", ")}
        </p>

        <div className="explorer-tabs" role="tablist" aria-label={titleText}>
          <button
            type="button"
            role="tab"
            id="tab-chart"
            aria-selected={view === "chart"}
            aria-controls="panel-chart"
            className={view === "chart" ? "is-active" : ""}
            onClick={() => setView("chart")}
          >
            {strings.chartTab}
          </button>
          <button
            type="button"
            role="tab"
            id="tab-table"
            aria-selected={view === "table"}
            aria-controls="panel-table"
            className={view === "table" ? "is-active" : ""}
            onClick={() => setView("table")}
          >
            {strings.tableTab}
          </button>
        </div>

        {view === "chart" && (
        <div id="panel-chart" role="tabpanel" aria-labelledby="tab-chart">
        <div className="explorer-controls">
          <label>
            <span>{strings.dimension}</span>
            <select value={dimension} onChange={(e) => setDimension(e.target.value)}>
              {table.dimensions.map((d) => (
                <option key={d} value={d}>
                  {label(labels, d)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{strings.measure}</span>
            <select value={measure} onChange={(e) => setMeasure(e.target.value)}>
              {table.measures.map((m) => (
                <option key={m} value={m}>
                  {label(labels, m)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{strings.chartType}</span>
            <select value={chartType} onChange={(e) => setChartType(e.target.value as ChartType)}>
              <option value="bar">{strings.bar}</option>
              <option value="pie">{strings.pie}</option>
              <option value="none">{strings.none}</option>
            </select>
          </label>
          <label>
            <span>{strings.topN}</span>
            <select value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
              {[5, 10, 15, 20, 30].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </div>

        {chartType !== "none" && groups.length > 0 && (
          <figure className="chart" aria-label={`${label(labels, measure)} — ${label(labels, dimension)}`}>
            <figcaption>
              {label(labels, measure)} — {label(labels, dimension)}
            </figcaption>
            {chartType === "bar" ? (
              <svg
                role="img"
                aria-label={`${label(labels, measure)} — ${label(labels, dimension)}`}
                viewBox={`0 0 720 ${groups.length * 40}`}
                width="100%"
                preserveAspectRatio="xMinYMin meet"
              >
                {groups.map((g, i) => {
                  const y = i * 40;
                  const w = max > 0 ? Math.max(2, (g.value / max) * 430) : 2;
                  return (
                    <g key={g.key}>
                      <text x={182} y={y + 15} textAnchor="end" dominantBaseline="middle" className="chart-label">
                        {g.key.length > 34 ? `${g.key.slice(0, 33)}…` : g.key}
                      </text>
                      <rect x={190} y={y} width={w} height={30} rx="3" className="chart-bar">
                        <title>{`${g.key}: ${nf.format(g.value)}`}</title>
                      </rect>
                      <text x={190 + w + 8} y={y + 15} dominantBaseline="middle" className="chart-value">
                        {nf.format(g.value)}
                      </text>
                    </g>
                  );
                })}
              </svg>
            ) : (
              <div className="pie-wrap">
                <svg role="img" aria-label={`${label(labels, measure)} — ${label(labels, dimension)}`} viewBox="0 0 200 200" width="220" height="220">
                  {(() => {
                    let angle = -Math.PI / 2;
                    return groups.map((g, i) => {
                      const frac = total > 0 ? g.value / total : 0;
                      const next = angle + frac * 2 * Math.PI;
                      const [x1, y1] = polar(100, 100, 90, angle);
                      const [x2, y2] = polar(100, 100, 90, next);
                      const large = frac > 0.5 ? 1 : 0;
                      const d = `M100,100 L${x1.toFixed(2)},${y1.toFixed(2)} A90,90 0 ${large} 1 ${x2.toFixed(2)},${y2.toFixed(2)} Z`;
                      angle = next;
                      return (
                        <path key={g.key} d={d} fill={PALETTE[i % PALETTE.length]}>
                          <title>{`${g.key}: ${nf.format(g.value)} (${(frac * 100).toFixed(1)}%)`}</title>
                        </path>
                      );
                    });
                  })()}
                  <circle cx="100" cy="100" r="45" fill="#fff" />
                </svg>
                <ul className="pie-legend" aria-hidden="true">
                  {groups.map((g, i) => (
                    <li key={g.key}>
                      <span className="pie-swatch" style={{ background: PALETTE[i % PALETTE.length] }} aria-hidden="true" />
                      {g.key}: {nf.format(g.value)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <table className="sr-only">
              <caption>{`${label(labels, measure)} — ${label(labels, dimension)}`}</caption>
              <thead>
                <tr>
                  <th scope="col">{label(labels, dimension)}</th>
                  <th scope="col">{label(labels, measure)}</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={g.key}>
                    <th scope="row">{g.key}</th>
                    <td>{nf.format(g.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </figure>
        )}
        {chartType !== "none" && groups.length === 0 && (
          <p className="explorer-empty">{strings.chartEmpty}</p>
        )}
        </div>
        )}

        {view === "table" && (
        <div id="panel-table" role="tabpanel" aria-labelledby="tab-table">
        <div className="explorer-filter">
          <label>
            <span>{strings.filter}</span>
            <input
              type="search"
              value={filter}
              placeholder={strings.filterPlaceholder}
              onChange={(e) => setFilter(e.target.value)}
            />
          </label>
          <span className="meta">
            {filteredRows.length} / {table.rows.length} {strings.rows}
          </span>
        </div>

        {filteredRows.length === 0 ? (
          <p className="explorer-empty">{strings.noResults}</p>
        ) : (
          <div className="table-scroll" tabIndex={0} role="region" aria-label={titleText}>
            <table className="data">
              <thead>
                <tr>
                  {table.columns.map((col) => (
                    <th key={col} scope="col">
                      {label(labels, col)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredRows.slice(0, 200).map((row, i) => (
                  <tr key={i}>
                    {table.columns.map((col) => (
                      <td key={col}>{row[col] ?? "—"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {filteredRows.length > 200 && (
          <p className="meta">
            {strings.showingTop} 200 / {filteredRows.length} {strings.rows}
          </p>
        )}
        </div>
        )}

        <p className="meta">
          {strings.apiHint}{" "}
          <code>
            {apiBase}/v1/datasets/{table.identifier}/data.csv
          </code>
        </p>
      </div>
    </div>
  );
}
