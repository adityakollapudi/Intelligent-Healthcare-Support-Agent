// Screens whose backend services arrive in later phases. They show real structure and honest
// availability, never sample records or metrics.
import { Link } from "react-router-dom";

import { EmptyState, FeatureUnavailable, PageHeader } from "../components/ui";
import { features } from "../lib/features";

export function AgentPage() {
  return (
    <>
      <PageHeader title="Case queue" description="Unassigned cases and cases assigned to you, with escalation reasons and linked evidence." />
      <FeatureUnavailable feature={features.agentWorkspace} />
      <EmptyState title="Queue is empty">No case data is available until the case-management service is connected.</EmptyState>
    </>
  );
}

export function AdminPage() {
  return (
    <>
      <PageHeader title="Admin dashboard" description="Aggregate metrics, knowledge gaps and audit events from the synthetic prototype environment." />
      <FeatureUnavailable feature={features.adminDashboard}>
        <p className="muted small">No metrics are shown until real aggregates are available, so nothing on this page is estimated or sample data.</p>
      </FeatureUnavailable>
    </>
  );
}

export function ProviderWorkspacePage() {
  return (
    <>
      <PageHeader title="Provider workspace" description="Start an administrative task for a fictional prior authorization request." />
      <div className="tiles">
        <Link className="tile" to="/benefits">
          <span className="tile-title">Look up plan benefits</span>
          <span className="muted small">Available now</span>
        </Link>
        <Link className="tile" to="/chat">
          <span className="tile-title">Ask about requirements</span>
          <span className="muted small">Available now</span>
        </Link>
        <Link className="tile" to="/documents">
          <span className="tile-title">Upload a document</span>
          <span className="muted small">Available now</span>
        </Link>
        <Link className="tile" to="/readiness">
          <span className="tile-title">Check readiness</span>
          <span className="muted small">Available now</span>
        </Link>
      </div>
    </>
  );
}
