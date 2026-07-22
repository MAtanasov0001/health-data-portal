import { describe, expect, it } from "vitest";

import { localizedTitle } from "@/lib/api";

describe("localizedTitle", () => {
  it("returns the requested locale when present", () => {
    expect(localizedTitle({ bg: "Заглавие", en: "Title" }, "en")).toBe("Title");
  });

  it("falls back to bg when the locale is missing", () => {
    expect(localizedTitle({ bg: "Заглавие" }, "en")).toBe("Заглавие");
  });

  it("falls back to any value when bg is missing", () => {
    expect(localizedTitle({ de: "Titel" }, "en")).toBe("Titel");
  });

  it("returns empty string for an empty map", () => {
    expect(localizedTitle({}, "bg")).toBe("");
  });
});
