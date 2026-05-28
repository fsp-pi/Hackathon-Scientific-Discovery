import { Link, useLocation } from "react-router-dom";
import clsx from "clsx";

import { useAuth } from "../auth";

const tabs = [
  { to: "/", label: "Browse" },
  { to: "/activity", label: "Activity" },
  { to: "/reviews", label: "Reviews" },
  { to: "/getting-started", label: "Getting Started" },
  { to: "/settings", label: "Settings" },
];

export function NavBar() {
  const { pathname } = useLocation();
  const { user, signOut } = useAuth();

  return (
    <nav className="nav">
      <span className="nav-brand">Scientific Discovery</span>
      <div className="nav-tabs">
        {tabs.map((t) => {
          const active = t.to === "/" ? pathname === "/" : pathname.startsWith(t.to);
          return (
            <Link key={t.to} to={t.to} className={clsx("nav-tab", active && "active")}>
              {t.label}
            </Link>
          );
        })}
      </div>
      <div className="nav-spacer" />
      <div className="nav-user">
        {user && <span>{user.teamName} · {user.email}</span>}
        <button className="button button-ghost" onClick={() => void signOut()}>
          Sign out
        </button>
      </div>
    </nav>
  );
}
