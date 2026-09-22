import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { describeReplaced, PrivacyPanel } from "@/components/assistant/privacy";

describe("privacy panel", () => {
  it("lists what was hidden in plain language, names first", () => {
    expect(describeReplaced({ date_of_birth: 1, mrn: 1, patient_name: 2 })).toBe("2 names, 1 record number and 1 date of birth");
    expect(describeReplaced({ phone: 1 })).toBe("1 phone number");
  });

  it("shows the request as sent, with every placeholder marked", async () => {
    render(<PrivacyPanel privacy={{ applied: true, destination: "groq", total: 2, replaced: { patient_name: 1, mrn: 1 },
      preview: "[R1] PATIENT_1, MRN MRN_1, 67-year-old female." }} />);
    expect(screen.getByText(/Before this question went to Groq, 1 name and 1 record number were replaced/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Show exactly what Groq received/ }));
    expect([...document.querySelectorAll("mark")].map((m) => m.textContent)).toEqual(["PATIENT_1", "MRN_1"]);
  });

  it("says plainly when the model runs inside the hospital network", () => {
    const { container } = render(<PrivacyPanel privacy={{ applied: false, destination: "openai_compatible", total: 0, replaced: {} }} />);
    expect(within(container).getByText(/runs inside the hospital network/)).toBeInTheDocument();
    expect(within(container).queryByRole("button")).not.toBeInTheDocument();
  });
});
