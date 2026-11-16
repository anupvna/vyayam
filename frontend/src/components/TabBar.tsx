// Bottom navigation, in thumb reach. Tabs are added here as features ship.
import { NavLink } from "react-router";

const ICONS: Record<string, string> = {
  today: "M4 9h16M8 3v4M16 3v4M5 6h14v14H5z",
  progress: "M4 19V5M4 19h16M8 15l4-4 3 3 5-6",
  plan: "M4 6h16M4 12h16M4 18h10",
  library: "M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM5 17a3 3 0 0 1 3-3h10M9 8h5",
  profile: "M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8zM4 21c1-4 4-6 8-6s7 2 8 6",
};

const TABS = [
  { to: "/", label: "Today", icon: "today" },
  { to: "/plan", label: "Plan", icon: "plan" },
  { to: "/progress", label: "Progress", icon: "progress" },
  { to: "/library", label: "Library", icon: "library" },

  { to: "/profile", label: "Profile", icon: "profile" },
];

export function TabBar() {
  return (
    <nav className="tabbar" aria-label="Main">
      {TABS.map((t) => (
        <NavLink key={t.to} to={t.to} end className={({ isActive }) => (isActive ? "active" : "")}>
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d={ICONS[t.icon]} />
          </svg>
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
