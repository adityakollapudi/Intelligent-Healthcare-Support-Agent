import { useState } from "react";

import { FileDropzone, type FileCheck } from "../components/FileDropzone";
import { Alert, Button, FeatureUnavailable, PageHeader } from "../components/ui";
import { features } from "../lib/features";
import { formatBytes } from "../lib/format";

export function DocumentsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [check, setCheck] = useState<FileCheck | null>(null);
  const uploadReady = features.documents.available && check?.ok;

  return (
    <>
      <PageHeader
        title="Documents"
        description="Upload a synthetic sample document to extract and check its fields. Every extracted value must be reviewed by you."
      />
      <FeatureUnavailable feature={features.documents} />
      <section className="section card" aria-labelledby="upload-heading">
        <h2 id="upload-heading">Select a document</h2>
        <FileDropzone
          onSelect={(f, c) => {
            setFile(f);
            setCheck(c);
          }}
        />
        {file && check && (
          <div className="selected-file" aria-live="polite">
            <p>
              <strong>{file.name}</strong> <span className="muted">· {formatBytes(file.size)}</span>
            </p>
            {check.ok ? (
              <Alert tone="success" title="Passes basic checks">
                Type and size look acceptable. The server performs its own validation when upload is connected.
              </Alert>
            ) : (
              <Alert tone="danger" title="This file can't be used">
                {check.reason}
              </Alert>
            )}
            <div className="row">
              <Button disabled={!uploadReady} aria-describedby="upload-disabled-reason">
                Upload and analyze
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setFile(null);
                  setCheck(null);
                }}
              >
                Remove file
              </Button>
            </div>
            {!features.documents.available && (
              <p id="upload-disabled-reason" className="muted small">
                Upload is disabled until the document service is implemented (Phase {features.documents.phase}). The file
                stays on your device.
              </p>
            )}
          </div>
        )}
      </section>
      <section className="section" aria-labelledby="results-heading">
        <h2 id="results-heading">Analysis results</h2>
        <p className="muted">No analysis has run. Results (extracted fields, warnings and page references) will appear here once the service is connected.</p>
      </section>
    </>
  );
}
