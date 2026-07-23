import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SiteFooter from "@/components/SiteFooter";
import bg from "@/lib/dictionaries/bg.json";

describe("SiteFooter a11y", () => {
  it("exposes a contentinfo landmark and a source-code link", () => {
    render(<SiteFooter lang="bg" dict={bg} />);
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: bg.footer.repo })).toBeInTheDocument();
  });
});
