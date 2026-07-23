import type { SummaryGroup } from "@/lib/api";
import { numberFormat } from "@/lib/format";

interface Props {
  groups: SummaryGroup[];
  title: string;
  valueLabel: string;
  lang: string;
  keyLabel?: string;
}

// Хоризонтална стълбовидна графика на чист SVG (без зависимости). Достъпна: контейнерът е
// figure с заглавие, SVG е role="img" с aria-label, а всяка стълба носи <title> с точната
// стойност. За екранни четци има и еквивалентна скрита таблица със същите числа.
export default function BarChart({ groups, title, valueLabel, lang, keyLabel }: Props) {
  if (groups.length === 0) return null;

  const nf = numberFormat(lang);

  const max = Math.max(...groups.map((g) => g.value));
  const rowH = 30;
  const gap = 10;
  const labelW = 190;
  const barW = 430;
  const pad = 8;
  const height = groups.length * (rowH + gap) - gap;
  const width = labelW + barW + 90;

  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <svg
        role="img"
        aria-label={title}
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        preserveAspectRatio="xMinYMin meet"
      >
        {groups.map((g, i) => {
          const y = i * (rowH + gap);
          const w = max > 0 ? Math.max(2, (g.value / max) * barW) : 2;
          return (
            <g key={g.key}>
              <text
                x={labelW - pad}
                y={y + rowH / 2}
                textAnchor="end"
                dominantBaseline="middle"
                className="chart-label"
              >
                {g.key}
              </text>
              <rect x={labelW} y={y} width={w} height={rowH} rx="3" className="chart-bar">
                <title>{`${g.key}: ${nf.format(g.value)} ${valueLabel}`}</title>
              </rect>
              <text
                x={labelW + w + pad}
                y={y + rowH / 2}
                dominantBaseline="middle"
                className="chart-value"
              >
                {nf.format(g.value)}
              </text>
            </g>
          );
        })}
      </svg>
      <table className="sr-only">
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">{keyLabel ?? title}</th>
            <th scope="col">{valueLabel}</th>
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
  );
}
