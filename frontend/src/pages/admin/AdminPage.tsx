import { useQuery } from "@tanstack/react-query";
import { api, call, type BookingStatus } from "../../api/client";
import { Card, ErrorNotice, PageHeader, Spinner } from "../../components/ui";
import { BOOKING_STATUS } from "../../lib/format";
import { BookingsList } from "../BookingsList";

const HIGHLIGHTED: BookingStatus[] = ["PENDING", "ACCEPTED", "REJECTED", "CANCELLED"];
const ACCENTS: Record<string, string> = {
  PENDING: "text-amber-600",
  ACCEPTED: "text-emerald-600",
  REJECTED: "text-rose-600",
  CANCELLED: "text-slate-500",
};

export function AdminPage() {
  const stats = useQuery({ queryKey: ["stats"], queryFn: () => call(api.GET("/api/admin/stats")) });

  return (
    <>
      <PageHeader title="Tableau de bord" description="Toutes les demandes de la plateforme et leur statut." />
      {stats.isPending ? (
        <Spinner />
      ) : stats.isError ? (
        <ErrorNotice error={stats.error} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <Card className="p-5">
              <p className="text-sm text-slate-500">Demandes</p>
              <p className="mt-1 text-3xl font-semibold tabular-nums text-slate-900">
                {Object.values(stats.data.byStatus).reduce((sum, count) => sum + count, 0)}
              </p>
            </Card>
            {HIGHLIGHTED.map((status) => (
              <Card key={status} className="p-5">
                <p className="text-sm text-slate-500">{BOOKING_STATUS[status].label}</p>
                <p className={`mt-1 text-3xl font-semibold tabular-nums ${ACCENTS[status]}`}>{stats.data.byStatus[status] ?? 0}</p>
              </Card>
            ))}
          </div>
          <Card className="mt-6 p-5">
            <h2 className="font-semibold text-slate-900">Demandes par chantier</h2>
            <ul className="mt-4 space-y-3">
              {stats.data.byShipyard.map((shipyard) => {
                const max = Math.max(1, ...stats.data.byShipyard.map((s) => s.total));
                return (
                  <li key={shipyard.shipyardId} className="grid grid-cols-[minmax(0,14rem)_1fr_2rem] items-center gap-3 text-sm">
                    <span className="truncate text-slate-700">{shipyard.name}</span>
                    <span className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <span className="block h-full rounded-full bg-brand-500" style={{ width: `${(shipyard.total / max) * 100}%` }} />
                    </span>
                    <span className="text-right tabular-nums text-slate-600">{shipyard.total}</span>
                  </li>
                );
              })}
            </ul>
          </Card>
        </>
      )}
      <h2 className="mb-4 mt-10 text-lg font-semibold text-slate-900">Toutes les demandes</h2>
      <BookingsList empty="Aucune demande avec ce statut." />
    </>
  );
}
