import type { ChecklistItem, ChecklistItemStatus } from "../types/api";
import { CHECKLIST_STATUS_META, MetaBadge } from "./status";

export const READINESS_DISCLAIMER =
  "This checklist reviews documentation completeness only. It is not an authorization approval, denial, medical-necessity determination, or guarantee of coverage.";

/** Renders a backend checklist; it never computes item statuses itself. */
export function ChecklistView({ items }: { items: ChecklistItem[] }) {
  return (
    <ul className="checklist">
      {items.map((item) => (
        <li key={item.requirement_code} className="checklist-item">
          <MetaBadge meta={CHECKLIST_STATUS_META[item.item_status]} />
          <div>
            <p>
              <span className="mono">{item.requirement_code}</span> {item.description}
            </p>
            <p className="muted small">{item.explanation}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function ChecklistLegend() {
  return (
    <dl className="legend">
      {(Object.keys(CHECKLIST_STATUS_META) as ChecklistItemStatus[]).map((status) => (
        <div key={status}>
          <dt>
            <MetaBadge meta={CHECKLIST_STATUS_META[status]} />
          </dt>
          <dd>{CHECKLIST_STATUS_META[status].help}</dd>
        </div>
      ))}
    </dl>
  );
}
