import { useQuery } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";
import { useState, type ReactNode } from "react";
import { api, call, type Booking, type BookingStatus } from "../api/client";
import { BookingCard } from "../components/BookingCard";
import { OwnerCancel, YardDecision } from "../components/BookingActions";
import { EmptyState, ErrorNotice, Spinner, Tabs } from "../components/ui";
import { useCurrentUser } from "../auth";

const FILTERS: { value: BookingStatus | undefined; label: string }[] = [
  { value: "PENDING", label: "En attente" },
  { value: "ACCEPTED", label: "Acceptées" },
  { value: "REJECTED", label: "Refusées" },
  { value: "CANCELLED", label: "Annulées" },
  { value: undefined, label: "Toutes" },
];

/** Liste des réservations visibles par l'utilisateur (filtrées par l'API selon son rôle). */
export function BookingsList({ initialStatus, empty }: { initialStatus?: BookingStatus; empty: ReactNode }) {
  const me = useCurrentUser();
  const [status, setStatus] = useState<BookingStatus | undefined>(initialStatus);
  const bookings = useQuery({
    queryKey: ["bookings", status ?? "ALL"],
    queryFn: () => call(api.GET("/api/bookings", { params: { query: { status } } })),
  });
  // Demandes en attente par créneau : signale au chantier les demandes concurrentes.
  const pending = useQuery({
    queryKey: ["bookings", "PENDING"],
    queryFn: () => call(api.GET("/api/bookings", { params: { query: { status: "PENDING" } } })),
    enabled: me.role === "YARD",
  });
  const rivals = (booking: Booking) => pending.data?.filter((other) => other.slot.id === booking.slot.id).length ?? 0;

  return (
    <>
      <Tabs value={status} options={FILTERS} onChange={setStatus} />
      {bookings.isPending ? (
        <Spinner />
      ) : bookings.isError ? (
        <ErrorNotice error={bookings.error} />
      ) : bookings.data.length === 0 ? (
        <EmptyState icon={ClipboardList} title="Aucune réservation">
          {empty}
        </EmptyState>
      ) : (
        <div className="grid gap-4">
          {bookings.data.map((booking) => (
            <BookingCard key={booking.id} booking={booking} viewer={me.role} rivals={rivals(booking)}>
              {booking.status === "PENDING" && me.role === "YARD" && <YardDecision booking={booking} rivals={rivals(booking)} />}
              {booking.status === "PENDING" && me.role === "OWNER" && <OwnerCancel booking={booking} />}
            </BookingCard>
          ))}
        </div>
      )}
    </>
  );
}
