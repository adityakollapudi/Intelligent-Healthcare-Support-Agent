const dateFmt = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** Calendar date (YYYY-MM-DD) shown without timezone shifting. */
export function formatDate(isoDate: string): string {
  const d = new Date(`${isoDate.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? isoDate : dateFmt.format(d);
}

/** UTC timestamp shown in the viewer's local time. */
export function formatDateTime(isoTimestamp: string): string {
  const d = new Date(isoTimestamp);
  return Number.isNaN(d.getTime()) ? isoTimestamp : dateTimeFmt.format(d);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function humanize(code: string): string {
  return code.charAt(0) + code.slice(1).toLowerCase().replace(/_/g, " ");
}
