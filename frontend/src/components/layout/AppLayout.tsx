import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { visibleNav } from "../../app/navigation";
import { useSession } from "../../features/auth/session";
import { humanize } from "../../lib/format";
import { HealthIndicator } from "./HealthIndicator";

export function AppLayout() {
  const { user, signOut } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const items = visibleNav(user?.permissions ?? []);

  // Close the mobile drawer after navigating.
  useEffect(() => setMenuOpen(false), [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <header className="topbar">
        <button
          type="button"
          className="menu-toggle"
          aria-expanded={menuOpen}
          aria-controls="primary-nav"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span aria-hidden="true">☰</span>
          <span className="sr-only">{menuOpen ? "Close navigation" : "Open navigation"}</span>
        </button>
        <span className="wordmark">
          IHSA <span className="wordmark-sub">Healthcare Support</span>
        </span>
        <HealthIndicator />
        <div className="user-box">
          <span className="user-name">{user?.display_name}</span>
          <span className="user-role">{user ? humanize(user.role) : ""}</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </header>

      <nav id="primary-nav" className={`sidebar ${menuOpen ? "open" : ""}`} aria-label="Primary">
        <ul>
          {items.map((item) => (
            <li key={item.path}>
              <NavLink to={item.path} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
        <p className="sidebar-note">Synthetic prototype data · not an Evernorth product</p>
      </nav>
      {menuOpen && <div className="scrim" aria-hidden="true" onClick={() => setMenuOpen(false)} />}

      <main id="main" className="main" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="footer">Prototype using synthetic data — not a real insurance service.</footer>
    </div>
  );
}
