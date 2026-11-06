import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand">
            confirmAI
          </NavLink>
          <nav className="nav">
            <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
              Verify
            </NavLink>
            <NavLink to="/history" className={({ isActive }) => (isActive ? "active" : "")}>
              History
            </NavLink>
            <NavLink to="/rules" className={({ isActive }) => (isActive ? "active" : "")}>
              Rules
            </NavLink>
          </nav>
          <span className="topbar-label">EINKAUF · PROCUREMENT</span>
        </div>
      </header>
      <main className="page">{children}</main>
    </div>
  );
}
