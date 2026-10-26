import { NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { roleLabel } from "../lib/format";

const TABS = [
  { to: "/register", label: "Register", managerOnly: false },
  { to: "/inventory", label: "Inventory", managerOnly: true },
  { to: "/orders", label: "Orders", managerOnly: true },
  { to: "/staff", label: "Staff", managerOnly: true },
];

export default function TopBar() {
  const { user, isManager, signOut } = useAuth();
  const navigate = useNavigate();

  const visible = TABS.filter((tab) => isManager || !tab.managerOnly);

  return (
    <header className="topbar">
      <div className="brand">
        <div className="logo-tile" aria-hidden="true">
          तु
        </div>
        <div>
          <div className="brand-name">Tulsi Tiffins</div>
          <div className="brand-sub">Point of Sale</div>
        </div>
      </div>

      <nav className="tabs" aria-label="Sections">
        {visible.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) => `tab${isActive ? " is-active" : ""}`}
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>

      <div className="topbar-right">
        <div className="role-caption">{roleLabel(user?.role)}</div>
        <div className="user-chip">
          <span>{user?.name}</span>
          <button
            type="button"
            className="signout"
            onClick={() => {
              signOut();
              navigate("/login", { replace: true });
            }}
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
