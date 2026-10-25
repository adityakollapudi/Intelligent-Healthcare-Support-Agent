// Frontend-safe configuration only. VITE_* values are public: never put secrets here.

function readBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const value = (raw ?? "").trim().replace(/\/+$/, "");
  if (!value) {
    // Fails loudly in development instead of silently calling a wrong host.
    throw new Error("VITE_API_BASE_URL is not set. Copy frontend/.env.example to .env.local.");
  }
  return value;
}

function readTimeout(): number {
  const parsed = Number(import.meta.env.VITE_API_TIMEOUT_MS);
  return Number.isFinite(parsed) && parsed >= 1000 ? parsed : 15000;
}

export const config = {
  apiBaseUrl: readBaseUrl(),
  requestTimeoutMs: readTimeout(),
  // Mirrors backend defaults (doc 07 §5.1); the backend re-validates every upload.
  maxUploadBytes: 10 * 1024 * 1024,
  acceptedUploadTypes: {
    "application/pdf": [".pdf"],
    "image/png": [".png"],
    "image/jpeg": [".jpg", ".jpeg"],
  } as Record<string, string[]>,
} as const;
