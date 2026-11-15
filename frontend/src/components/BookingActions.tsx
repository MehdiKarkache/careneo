import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ApiError, api, call, type Booking } from "../api/client";
import { Button, Field, inputClass } from "./ui";

function useRefreshAll() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries();
}

/** Décision du chantier sur une demande en attente. */
export function YardDecision({ booking, rivals = 0 }: { booking: Booking; rivals?: number }) {
  const refresh = useRefreshAll();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const path = { params: { path: { id: booking.id } } };

  const accept = useMutation({
    mutationFn: () => call(api.POST("/api/bookings/{id}/accept", path)),
    onSuccess: () => {
      toast.success(
        rivals > 1
          ? `Créneau attribué. ${rivals - 1} demande(s) concurrente(s) refusée(s) automatiquement.`
          : "Demande acceptée : le créneau est attribué.",
      );
      void refresh();
    },
    onError: (error) => toast.error(error.message),
  });
  const reject = useMutation({
    mutationFn: () => call(api.POST("/api/bookings/{id}/reject", { ...path, body: { reason } })),
    onSuccess: () => {
      toast.success("Demande refusée");
      void refresh();
    },
    onError: (error) => {
      if (!(error instanceof ApiError && error.details.reason)) toast.error(error.message);
    },
  });

  if (rejecting) {
    const reasonError = reject.error instanceof ApiError ? reject.error.details.reason : undefined;
    return (
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          reject.mutate();
        }}
      >
        <Field label="Motif du refus" error={reasonError} hint="Visible par l'armateur.">
          <textarea
            className={inputClass}
            rows={2}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            aria-invalid={Boolean(reasonError)}
            placeholder="Ex. : poste indisponible pour maintenance"
            autoFocus
          />
        </Field>
        <div className="flex gap-2">
          <Button type="submit" variant="danger" loading={reject.isPending}>
            Confirmer le refus
          </Button>
          <Button variant="secondary" onClick={() => setRejecting(false)}>
            Annuler
          </Button>
        </div>
      </form>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="success" onClick={() => accept.mutate()} loading={accept.isPending}>
        <Check className="size-4" aria-hidden />
        Accepter
      </Button>
      <Button variant="secondary" onClick={() => setRejecting(true)} disabled={accept.isPending}>
        <X className="size-4" aria-hidden />
        Refuser
      </Button>
      {rivals > 1 && (
        <span className="text-xs text-slate-500">
          Accepter refusera automatiquement les {rivals - 1} autre(s) demande(s) sur ce créneau.
        </span>
      )}
    </div>
  );
}

/** Annulation d'une demande en attente par l'armateur, avec confirmation. */
export function OwnerCancel({ booking }: { booking: Booking }) {
  const refresh = useRefreshAll();
  const [confirming, setConfirming] = useState(false);
  const cancel = useMutation({
    mutationFn: () => call(api.POST("/api/bookings/{id}/cancel", { params: { path: { id: booking.id } } })),
    onSuccess: () => {
      toast.success("Demande annulée");
      void refresh();
    },
    onError: (error) => toast.error(error.message),
  });

  if (!confirming) {
    return (
      <Button variant="secondary" onClick={() => setConfirming(true)}>
        Annuler la demande
      </Button>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-slate-600">Annuler cette demande ?</span>
      <Button variant="danger" onClick={() => cancel.mutate()} loading={cancel.isPending}>
        Oui, annuler
      </Button>
      <Button variant="ghost" onClick={() => setConfirming(false)}>
        Non
      </Button>
    </div>
  );
}
