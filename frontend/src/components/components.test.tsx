import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";
import { checkFile, FileDropzone } from "./FileDropzone";
import { SourceCitationList } from "./SourceCitation";
import { CLAIM_STATUS_META, MetaBadge } from "./status";

const file = (name: string, type: string, size: number) => new File([new Uint8Array(size)], name, { type });

describe("checkFile (usability only; backend re-validates)", () => {
  it.each([
    ["a.pdf", "application/pdf", 10, true],
    ["scan.JPG", "image/jpeg", 10, true],
    ["a.exe", "application/octet-stream", 10, false],
    ["fake.pdf", "image/png", 10, false],
    ["empty.pdf", "application/pdf", 0, false],
    ["big.pdf", "application/pdf", 10 * 1024 * 1024 + 1, false],
  ] as const)("%s (%s, %d bytes) → ok=%s", (name, type, size, ok) => {
    expect(checkFile(file(name, type, size)).ok).toBe(ok);
  });
});

describe("FileDropzone", () => {
  it("reports the chosen file and its check", async () => {
    const onSelect = vi.fn();
    render(<FileDropzone onSelect={onSelect} />);
    await userEvent.upload(screen.getByLabelText("Choose file"), file("a.pdf", "application/pdf", 5));
    expect(onSelect).toHaveBeenCalledWith(expect.any(File), { ok: true });
  });
});

describe("status badges", () => {
  it("always pair an icon with text", () => {
    render(<MetaBadge meta={CLAIM_STATUS_META.PROCESSED_DENIED} />);
    expect(screen.getByText("Processed – denied")).toBeInTheDocument();
    expect(screen.getByText("✖")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("SourceCitationList", () => {
  it("renders nothing without citations", () => {
    const { container } = render(<SourceCitationList citations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows title, version, pages and excerpt as text", () => {
    render(
      <SourceCitationList
        citations={[{ marker: "C1", chunk_id: "c", document_id: "d", document_title: "Guide", document_type: "FAQ", document_version: "2.0", effective_date: "2026-01-01", section_heading: "Intro", page_start: 3, page_end: 4, excerpt: "<b>bold?</b>" }]}
      />,
    );
    expect(screen.getByText("pp. 3–4")).toBeInTheDocument();
    expect(screen.getByText("<b>bold?</b>")).toBeInTheDocument();
    expect(screen.getByText(/Effective/)).toBeInTheDocument();
  });
});

describe("ConfirmDialog", () => {
  it("focuses the first button, traps Tab, and confirms", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog open title="Sure?" confirmLabel="Yes" onConfirm={onConfirm} onCancel={vi.fn()}>
        body
      </ConfirmDialog>,
    );
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "Yes" })).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Yes" }));
    expect(onConfirm).toHaveBeenCalled();
  });
});
