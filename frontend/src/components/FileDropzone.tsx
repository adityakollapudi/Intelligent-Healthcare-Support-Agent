import { useId, useRef, useState, type DragEvent } from "react";

import { config } from "../lib/config";
import { formatBytes } from "../lib/format";

export interface FileCheck {
  ok: boolean;
  reason?: string;
}

/** Usability checks only; the backend validates type, size and content independently. */
export function checkFile(file: File): FileCheck {
  const ext = file.name.includes(".") ? `.${file.name.split(".").pop()!.toLowerCase()}` : "";
  const allowedExts = Object.values(config.acceptedUploadTypes).flat();
  if (!allowedExts.includes(ext)) return { ok: false, reason: "Only PDF, PNG and JPEG files are supported." };
  if (file.type && !(config.acceptedUploadTypes[file.type] ?? []).includes(ext)) {
    return { ok: false, reason: "The file type doesn't match its extension." };
  }
  if (file.size === 0) return { ok: false, reason: "This file is empty." };
  if (file.size > config.maxUploadBytes) return { ok: false, reason: `Files must be ${formatBytes(config.maxUploadBytes)} or smaller.` };
  return { ok: true };
}

export function FileDropzone({ onSelect }: { onSelect: (file: File | null, check: FileCheck | null) => void }) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const choose = (file: File | undefined) => (file ? onSelect(file, checkFile(file)) : onSelect(null, null));

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    choose(e.dataTransfer.files[0]);
  };

  return (
    <div
      className={`dropzone ${dragging ? "dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <p className="state-title">Drop a file here or choose one</p>
      <p className="muted small">PDF, PNG or JPEG · up to {formatBytes(config.maxUploadBytes)} · synthetic sample documents only</p>
      <label htmlFor={inputId} className="btn btn-secondary">
        Choose file
      </label>
      <input
        ref={inputRef}
        id={inputId}
        className="sr-only"
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
        onChange={(e) => choose(e.target.files?.[0])}
      />
    </div>
  );
}
