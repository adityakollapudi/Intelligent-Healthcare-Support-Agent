// Provider workspace landing page (links to the implemented provider tasks).
import { Link } from "react-router-dom";

import { PageHeader } from "../components/ui";

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
