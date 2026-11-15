import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CalendarRange, Clock, MessageSquare, Ruler } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api, call } from "../api/client";
import { useCurrentUser } from "../auth";
import { indicativeTotal } from "../components/BookingCard";
import { OwnerCancel, YardDecision } from "../components/BookingActions";
import { BookingStatusBadge, Card, ErrorNotice, Spinner } from "../components/ui";
import { BOOKING_STATUS, DOCK_TYPES, VESSEL_TYPES, formatDateTime, formatEuros, formatMeters, formatPeriod } from "../lib/format";

export function BookingDetailPage() {
  const { id = "" } = useParams();
  const me = useCurrentUser();
  const navigate = useNavigate();
  const booking = useQuery({
    queryKey: ["booking", id],
    queryFn: () => call(api.GET("/api/bookings/{id}", { params: { path: { id } } })),
  });
  // Pour le chantier : nombre de demandes en attente sur le même créneau.
  const pending = useQuery({
    queryKey: ["bookings", "PENDING"],
    queryFn: () => call(api.GET("/api/bookings", { params: { query: { status: "PENDING" } } })),
    enabled: me.role === "YARD",
  });

  if (booking.isPending) return <Spinner />;
  if (booking.isError) return <ErrorNotice error={booking.error} />;
  const { vessel, slot, requestedBy, services, events } = booking.data;
  const total = indicativeTotal(booking.data);
  const rivals = pending.data?.filter((other) => other.slot.id === slot.id).length ?? 0;

  return (
    <>
      <button type="button" onClick={() => navigate(-1)} className="mb-4 flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900">
        <ArrowLeft className="size-4" aria-hidden />
        Retour
      </button>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Carénage de {vessel.name}</h1>
        <BookingStatusBadge status={booking.data.status} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-6">
          <Card className="divide-y divide-slate-100">
            <dl className="grid gap-5 p-5 sm:grid-cols-2">
              <Item label="Navire">
                {vessel.name}
                <span className="block text-sm text-slate-500">
                  {VESSEL_TYPES[vessel.type]} · IMO {vessel.imo}
                </span>
              </Item>
              <Item label="Demandeur">
                {requestedBy.name}
                <span className="block text-sm text-slate-500">{requestedBy.companyName}</span>
              </Item>
              <Item label="Chantier">
                {slot.shipyard.name}
                <span className="block text-sm text-slate-500">{slot.shipyard.port.name}</span>
              </Item>
              <Item label="Créneau">
                <span className="flex items-center gap-1.5">
                  <CalendarRange className="size-4 text-slate-400" aria-hidden />
                  {formatPeriod(slot.startDate, slot.endDate)}
                </span>
              </Item>
              <Item label="Poste">
                {slot.dock.name} · {DOCK_TYPES[slot.dock.type]}
                <span className="flex items-center gap-1.5 text-sm text-slate-500">
                  <Ruler className="size-3.5" aria-hidden />
                  {formatMeters(slot.dock.maxLengthM)} × {formatMeters(slot.dock.maxBeamM)} × {formatMeters(slot.dock.maxDraftM)}
                </span>
              </Item>
              <Item label="Envoyée le">{formatDateTime(booking.data.createdAt)}</Item>
            </dl>
            <div className="p-5">
              <h2 className="text-sm font-medium text-slate-500">Services demandés</h2>
              <ul className="mt-2 divide-y divide-slate-100 text-sm">
                {services.map((service) => (
                  <li key={service.id} className="flex justify-between py-2">
                    <span>{service.name}</span>
                    <span className="tabular-nums text-slate-600">{service.indicativePrice !== undefined ? formatEuros(service.indicativePrice) : "Sur devis"}</span>
                  </li>
                ))}
              </ul>
              {total > 0 && <p className="mt-2 text-right text-sm font-medium text-slate-900">Total indicatif : {formatEuros(total)} HT</p>}
            </div>
            {booking.data.message && (
              <p className="flex gap-2 p-5 text-sm text-slate-600">
                <MessageSquare className="mt-0.5 size-4 shrink-0 text-slate-400" aria-hidden />« {booking.data.message} »
              </p>
            )}
            {booking.data.rejectionReason && <p className="bg-rose-50 p-5 text-sm text-rose-700">Motif du refus : {booking.data.rejectionReason}</p>}
          </Card>

          {booking.data.status === "PENDING" && (me.role === "YARD" || me.role === "OWNER") && (
            <Card className="p-5">{me.role === "YARD" ? <YardDecision booking={booking.data} rivals={rivals} /> : <OwnerCancel booking={booking.data} />}</Card>
          )}
        </div>

        <Card className="h-fit p-5">
          <h2 className="flex items-center gap-2 font-semibold text-slate-900">
            <Clock className="size-4 text-slate-400" aria-hidden />
            Historique
          </h2>
          <ol className="mt-4 space-y-5 border-l border-slate-200 pl-5">
            {events.map((event) => (
              <li key={event.id} className="relative">
                <span className="absolute -left-[1.6rem] top-1 size-2.5 rounded-full bg-brand-500 ring-4 ring-white" aria-hidden />
                <p className="text-sm font-medium text-slate-900">
                  {event.fromStatus ? `${BOOKING_STATUS[event.fromStatus].label} → ${BOOKING_STATUS[event.toStatus].label}` : "Demande envoyée"}
                </p>
                <p className="text-xs text-slate-500">
                  {event.actorName} · {formatDateTime(event.createdAt)}
                </p>
                {event.comment && <p className="mt-1 text-sm text-slate-600">« {event.comment} »</p>}
              </li>
            ))}
          </ol>
          {me.role === "OWNER" && (
            <Link to="/reservations" className="mt-6 block text-sm font-medium text-brand-600 hover:underline">
              Toutes mes réservations
            </Link>
          )}
        </Card>
      </div>
    </>
  );
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm font-medium text-slate-500">{label}</dt>
      <dd className="mt-1 text-slate-900">{children}</dd>
    </div>
  );
}
