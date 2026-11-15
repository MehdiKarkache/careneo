import { Anchor, CalendarRange, ClipboardList, Inbox, LayoutDashboard, LogOut, Search, Ship } from "lucide-react";
import type { ComponentType } from "react";
import { Link, NavLink, Outlet } from "react-router";
import type { Me, Role } from "../api/client";
import { useLogout } from "../auth";
import { ROLES } from "../lib/format";

const NAVIGATION: Record<Role, { to: string; label: string; icon: ComponentType<{ className?: string }> }[]> = {
  OWNER: [
    { to: "/recherche", label: "Rechercher un créneau", icon: Search },
    { to: "/reservations", label: "Mes réservations", icon: ClipboardList },
    { to: "/navires", label: "Ma flotte", icon: Ship },
  ],
  YARD: [
    { to: "/demandes", label: "Demandes reçues", icon: Inbox },
    { to: "/chantier", label: "Postes et créneaux", icon: CalendarRange },
  ],
  ADMIN: [{ to: "/admin", label: "Tableau de bord", icon: LayoutDashboard }],
};

export function Layout({ me }: { me: Me }) {
  const logout = useLogout();
  return (
    <div className="min-h-screen">
      <header className="bg-brand-900 text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
            <Anchor className="size-5 text-sea-400" aria-hidden />
            Carénéo
          </Link>
          <nav className="flex flex-1 flex-wrap gap-1" aria-label="Navigation principale">
            {NAVIGATION[me.role].map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition ${isActive ? "bg-white/15 text-white" : "text-brand-100 hover:bg-white/10 hover:text-white"}`
                }
              >
                <Icon className="size-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <div className="text-right text-sm leading-tight">
              <div className="font-medium">{me.name}</div>
              <div className="text-xs text-brand-100">
                {ROLES[me.role]}
                {me.company && ` · ${me.company.name}`}
              </div>
            </div>
            <button
              type="button"
              onClick={() => logout.mutate()}
              className="rounded-lg p-2 text-brand-100 transition hover:bg-white/10 hover:text-white"
              title="Se déconnecter"
              aria-label="Se déconnecter"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
