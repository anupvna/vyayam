// Bottom navigation, in thumb reach. Tabs are added here as features ship.
import { NavLink } from "react-router";

const ICONS: Record<string, string> = {
  today: "M4 9h16M8 3v4M16 3v4M5 6h14v14H5z",
  gym: "M3 10v4M6 8v8M18 8v8M21 10v4M6 12h12",
  profile: "M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8zM4 21c1-4 4-6 8-6s7 2 8 6",
};

const TABS = [
  { to: "/", label: "Today", icon: "today" },
  { to: "/gyms", label: "Gym", icon: "gym" },
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
