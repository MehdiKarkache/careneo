import { Anchor } from "lucide-react";
import { Link, Navigate, Outlet, createBrowserRouter } from "react-router";
import type { Role } from "./api/client";
import { HOME, useMe } from "./auth";
import { Layout } from "./components/Layout";
import { EmptyState, ErrorNotice, PageHeader, Spinner } from "./components/ui";
import { AdminPage } from "./pages/admin/AdminPage";
import { BookingDetailPage } from "./pages/BookingDetailPage";
import { BookingsList } from "./pages/BookingsList";
import { LoginPage } from "./pages/LoginPage";
import { SearchPage } from "./pages/owner/SearchPage";
import { VesselsPage } from "./pages/owner/VesselsPage";
import { ShipyardPage } from "./pages/yard/ShipyardPage";

/** Routes protégées : redirige vers la connexion sans session valide. */
function RequireSession() {
  const me = useMe();
  if (me.isPending) return <Spinner />;
  if (me.isError) return <ErrorNotice error={me.error} />;
  if (!me.data) return <Navigate to="/login" replace />;
  return <Layout me={me.data} />;
}

/** Confort d'interface : l'API applique de toute façon la même garde de rôle. */
function RequireRole({ roles }: { roles: Role[] }) {
  const { data } = useMe();
  return data && roles.includes(data.role) ? <Outlet /> : <Navigate to="/" replace />;
}

function Home() {
  const { data } = useMe();
  return data ? <Navigate to={HOME[data.role]} replace /> : null;
}

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireSession />,
    children: [
      { index: true, element: <Home /> },
      {
        element: <RequireRole roles={["OWNER"]} />,
        children: [
          { path: "recherche", element: <SearchPage /> },
          { path: "navires", element: <VesselsPage /> },
          {
            path: "reservations",
            element: (
              <>
                <PageHeader title="Mes réservations" description="Suivez vos demandes et la réponse des chantiers." />
                <BookingsList empty={<Link to="/recherche" className="font-medium text-brand-600 hover:underline">Rechercher un créneau</Link>} />
              </>
            ),
          },
        ],
      },
      {
        element: <RequireRole roles={["YARD"]} />,
        children: [
          {
            path: "demandes",
            element: (
              <>
                <PageHeader title="Demandes reçues" description="Acceptez ou refusez les demandes de réservation sur vos postes." />
                <BookingsList initialStatus="PENDING" empty="Aucune demande dans cette catégorie." />
              </>
            ),
          },
          { path: "chantier", element: <ShipyardPage /> },
        ],
      },
      {
        element: <RequireRole roles={["ADMIN"]} />,
        children: [{ path: "admin", element: <AdminPage /> }],
      },
      { path: "reservations/:id", element: <BookingDetailPage /> },
      { path: "*", element: <EmptyState icon={Anchor} title="Page introuvable" /> },
    ],
  },
]);
