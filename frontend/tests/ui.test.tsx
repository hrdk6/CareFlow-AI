import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConfusionMatrix, DivergingBars } from "@/components/charts";
import { StatusBadge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/table";
import { cn, fmtDate, pct, titleCase } from "@/lib/format";

describe("formatting helpers", () => {
  it("formats values for clinical display", () => {
    expect(pct(0.2069)).toBe("20.7%");
    expect(pct(null)).toBe("—");
    expect(titleCase("home_health")).toBe("Home Health");
    expect(fmtDate("2026-09-05")).toBe("05 Sept 2026".replace("Sept", new Date("2026-09-05").toLocaleDateString("en-GB", { month: "short" })));
    expect(cn("a", false, null, "b")).toBe("a b");
  });
});

describe("components", () => {
  it("StatusBadge humanises statuses", () => {
    render(<StatusBadge status="checked_in" />);
    expect(screen.getByText("checked in")).toBeInTheDocument();
  });

  it("DataTable shows empty and error states", () => {
    const { rerender } = render(<DataTable rows={[]} columns={[{ key: "a", header: "A" }]} empty="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    rerender(<DataTable rows={undefined} error={new Error("Boom")} columns={[{ key: "a", header: "A" }]} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Boom");
  });

  it("DivergingBars labels direction of model factors", () => {
    render(<DivergingBars items={[{ label: "Prior admissions", detail: "3", value: 0.05 }, { label: "HbA1c", detail: "high 8", value: -0.01 }]} />);
    expect(screen.getByText("+0.050")).toHaveClass("text-high");
    expect(screen.getByText("-0.010")).toHaveClass("text-ok");
  });

  it("ConfusionMatrix shows counts", () => {
    render(<ConfusionMatrix tn={90} fp={10} fn={5} tp={15} />);
    expect(screen.getByText("90")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
  });
});
