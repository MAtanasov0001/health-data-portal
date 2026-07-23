import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import BarChart from "@/components/BarChart";
import type { SummaryGroup } from "@/lib/api";

const groups: SummaryGroup[] = [
  { key: "01 Благоевград", value: 1200, count: 3 },
  { key: "02 Бургас", value: 600, count: 2 },
];

describe("BarChart", () => {
  it("renders an accessible img with one bar per group", () => {
    const { container } = render(
      <BarChart
        groups={groups}
        title="Реимбурсна сума — РЗОК"
        valueLabel="Реимбурсна сума"
        lang="bg"
      />,
    );
    expect(screen.getByRole("img", { name: "Реимбурсна сума — РЗОК" })).toBeInTheDocument();
    expect(container.querySelectorAll("rect.chart-bar")).toHaveLength(2);
    // Скрита таблица-еквивалент за екранни четци носи същите стойности.
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("renders nothing for an empty dataset", () => {
    const { container } = render(<BarChart groups={[]} title="x" valueLabel="y" lang="bg" />);
    expect(container.firstChild).toBeNull();
  });
});
