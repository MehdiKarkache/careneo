import { CalendarRange, MessageSquare } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import type { Booking, Role } from "../api/client";
import { VESSEL_TYPES, formatDateTime, formatEuros, formatPeriod } from "../lib/format";
import { Badge, BookingStatusBadge, Card } from "./ui";

export function indicativeTotal(booking: Booking): number {
  return booking.services.reduce((sum, service) => sum + (service.indicativePrice ?? 0), 0);
}

export function BookingCard({ booking, viewer, rivals = 0, children }: { booking: Booking; viewer: Role; rivals?: number; children?: ReactNode }) {
  const { vessel, slot, requestedBy } = booking;
  const total = indicativeTotal(booking);
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <Link to={`/reservations/${booking.id}`} className="text-base font-semibold text-slate-900 hover:text-brand-600">
              {vessel.name}
            </Link>
            <span className="text-sm text-slate-500">
              {VESSEL_TYPES[vessel.type]} · IMO {vessel.imo}
            </span>
          </div>
          <p className="text-sm text-slate-700">
            {slot.shipyard.name} · {slot.shipyard.port.name} · {slot.dock.name}
          </p>
          <p className="flex items-center gap-1.5 text-sm text-slate-600">
            <CalendarRange className="size-4 text-slate-400" aria-hidden />
            {formatPeriod(slot.startDate, slot.endDate)}
          </p>
          {viewer !== "OWNER" && (
            <p className="text-xs text-slate-500">
              Demandée par {requestedBy.name} ({requestedBy.companyName}) le {formatDateTime(booking.createdAt)}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          <BookingStatusBadge status={booking.status} />
          {rivals > 1 && booking.status === "PENDING" && <Badge tone="amber">{rivals} demandes sur ce créneau</Badge>}
        </div>
      </div>
      <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Services demandés">
        {booking.services.map((service) => (
          <li key={service.id} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
            {service.name}
          </li>
        ))}
      </ul>
      {total > 0 && <p className="mt-2 text-xs text-slate-500">Total indicatif : {formatEuros(total)} HT</p>}
      {booking.message && (
        <p className="mt-3 flex gap-2 text-sm text-slate-600">
          <MessageSquare className="mt-0.5 size-4 shrink-0 text-slate-400" aria-hidden />« {booking.message} »
        </p>
      )}
      {booking.rejectionReason && (
        <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">Motif du refus : {booking.rejectionReason}</p>
      )}
      {children && <div className="mt-4 border-t border-slate-100 pt-4">{children}</div>}
    </Card>
  );
}
