import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DatasetSearch from "@/components/DatasetSearch";
import type { CollectionSummary, DatasetSummary } from "@/lib/api";

const datasets: DatasetSummary[] = [
  {
    identifier: "hosp-beds",
    uri: "u1",
    title: { bg: "Болнични легла", en: "Hospital beds" },
    version: "1.0.0",
    issued: "2026-01-01",
    row_count: 28,
    themes: ["HEAL"],
  },
  {
    identifier: "school-budget",
    uri: "u2",
    title: { bg: "Училищен бюджет", en: "School budget" },
    version: "1.0.0",
    issued: "2026-01-01",
    row_count: 10,
    themes: ["EDUC"],
  },
];

const collections: CollectionSummary[] = [];

const strings = {
  searchLabel: "Search",
  searchPlaceholder: "Search…",
  themeAll: "All themes",
  resultsOne: "1 result",
  resultsMany: "results",
  noResults: "No datasets match your search.",
  collectionsTitle: "Collections",
  collectionsLead: "lead",
  collectionBadge: "Collection",
  standaloneTitle: "Standalone",
  tables: "tables",
  rows: "Rows",
  version: "Version",
  issued: "Issued",
  empty: "empty",
};

const themeLabels = { HEAL: "Health", EDUC: "Education" };

function renderSearch() {
  return render(
    <DatasetSearch
      datasets={datasets}
      collections={collections}
      lang="en"
      strings={strings}
      themeLabels={themeLabels}
    />,
  );
}

describe("DatasetSearch", () => {
  it("filters datasets by free-text query", () => {
    renderSearch();
    expect(screen.getByText("Hospital beds")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "school" } });
    expect(screen.queryByText("Hospital beds")).not.toBeInTheDocument();
    expect(screen.getByText("School budget")).toBeInTheDocument();
  });

  it("filters by theme facet", () => {
    renderSearch();
    fireEvent.click(screen.getByRole("button", { name: "Health" }));
    expect(screen.getByText("Hospital beds")).toBeInTheDocument();
    expect(screen.queryByText("School budget")).not.toBeInTheDocument();
  });

  it("shows a no-results message when nothing matches", () => {
    renderSearch();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "zzz" } });
    expect(screen.getByText("No datasets match your search.")).toBeInTheDocument();
  });
});
