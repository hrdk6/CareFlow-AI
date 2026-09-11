import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Answer } from "@/components/assistant/answer";

describe("Answer renderer", () => {
  it("renders citations as clickable chips and reports the id", () => {
    const onCite = vi.fn();
    render(<Answer text={"Measure HbA1c every 3 months [S1]. Latest value 9.4% [R3]."} onCite={onCite} />);
    fireEvent.click(screen.getByRole("button", { name: "S1" }));
    fireEvent.click(screen.getByRole("button", { name: "R3" }));
    expect(onCite).toHaveBeenNthCalledWith(1, "S1");
    expect(onCite).toHaveBeenNthCalledWith(2, "R3");
  });

  it("renders lists, headings and emphasis", () => {
    const { container } = render(<Answer text={"## From hospital documents\n\n- **First** point\n- Second point\n\n1. one\n2. two"} />);
    expect(screen.getByRole("heading", { name: "From hospital documents" })).toBeInTheDocument();
    expect(container.querySelectorAll("ul li")).toHaveLength(2);
    expect(container.querySelectorAll("ol li")).toHaveLength(2);
    expect(screen.getByText("First").tagName).toBe("STRONG");
  });

  it("never interprets model output as HTML", () => {
    const { container } = render(<Answer text={'<img src=x onerror="alert(1)"> <script>alert(1)</script>'} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<img src=x");
  });
});
