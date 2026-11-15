import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, Check, Ruler, Search, Ship } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";
import { ApiError, api, call, type SearchResult, type Vessel } from "../../api/client";
import { Badge, Button, Card, EmptyState, ErrorNotice, Field, PageHeader, Spinner, inputClass } from "../../components/ui";
import { DOCK_TYPES, addDays, formatEuros, formatMeters, formatPeriod, toDay } from "../../lib/format";

type Criteria = { vesselId: string; portId: string; from: string; to: string };

export function SearchPage() {
  const vessels = useQuery({ queryKey: ["vessels"], queryFn: () => call(api.GET("/api/vessels")) });
  const ports = useQuery({ queryKey: ["ports"], queryFn: () => call(api.GET("/api/ports")) });
  const [draft, setDraft] = useState<Partial<Criteria>>({});
  const [criteria, setCriteria] = useState<Criteria | null>(null);

  const today = new Date();
  const form: Criteria = {
    vesselId: draft.vesselId ?? vessels.data?.[0]?.id ?? "",
    portId: draft.portId ?? ports.data?.find((port) => port.name === "Marseille")?.id ?? ports.data?.[0]?.id ?? "",
    from: draft.from ?? toDay(addDays(today, 1)),
    to: draft.to ?? toDay(addDays(today, 90)),
  };
  const update = (field: keyof Criteria) => (value: string) => setDraft((current) => ({ ...current, [field]: value }));

  const results = useQuery({
    queryKey: ["search", criteria],
    queryFn: () => call(api.GET("/api/search", { params: { query: criteria! } })),
    enabled: criteria !== null,
  });
  const vessel = vessels.data?.find((candidate) => candidate.id === criteria?.vesselId);
  const fieldErrors = results.error instanceof ApiError ? results.error.details : {};

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setCriteria(form);
  };

  if (vessels.isPending || ports.isPending) return <Spinner />;
  if (vessels.data?.length === 0) {
    return (
      <EmptyState icon={Ship} title="Aucun navire dans votre flotte">
        <Link to="/navires" className="font-medium text-brand-600 hover:underline">
          Ajoutez un navire
        </Link>{" "}
        pour rechercher un créneau compatible.
      </EmptyState>
    );
  }

  return (
    <>
      <PageHeader
        title="Rechercher un créneau de carénage"
        description="Seuls les postes qui acceptent la longueur, la largeur et le tirant d'eau de votre navire sont proposés."
      />
      <Card className="p-5">
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-[1.4fr_1fr_1fr_1fr_auto] md:items-end">
          <Field label="Navire">
            <select className={inputClass} value={form.vesselId} onChange={(e) => update("vesselId")(e.target.value)}>
              {vessels.data?.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} ({formatMeters(v.lengthM)})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Port">
            <select className={inputClass} value={form.portId} onChange={(e) => update("portId")(e.target.value)}>
              {ports.data?.map((port) => (
                <option key={port.id} value={port.id}>
                  {port.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Du" error={fieldErrors.from}>
            <input className={inputClass} type="date" value={form.from} onChange={(e) => update("from")(e.target.value)} required />
          </Field>
          <Field label="Au" error={fieldErrors.to}>
            <input className={inputClass} type="date" value={form.to} onChange={(e) => update("to")(e.target.value)} required />
          </Field>
          <Button type="submit" loading={results.isFetching}>
            <Search className="size-4" aria-hidden />
            Rechercher
          </Button>
        </form>
      </Card>

      <section className="mt-8">
        {criteria === null ? (
          <EmptyState icon={CalendarRange} title="Choisissez un navire, un port et une période">
            Les créneaux ouverts et compatibles s'afficheront ici.
          </EmptyState>
        ) : results.isPending ? (
          <Spinner label="Recherche des créneaux…" />
        ) : results.isError ? (
          Object.keys(fieldErrors).length === 0 && <ErrorNotice error={results.error} />
        ) : results.data.length === 0 ? (
          <EmptyState icon={Search} title="Aucun créneau compatible sur cette période">
            Élargissez la période ou essayez un autre port.
          </EmptyState>
        ) : (
          <>
            <p className="mb-4 text-sm text-slate-500">
              {results.data.length} créneau(x) compatible(s) avec {vessel?.name}
            </p>
            <div className="grid gap-4">
              {results.data.map((result) => vessel && <ResultCard key={result.slotId} result={result} vessel={vessel} />)}
            </div>
          </>
        )}
      </section>
    </>
  );
}

function ResultCard({ result, vessel }: { result: SearchResult; vessel: Vessel }) {
  const [requesting, setRequesting] = useState(false);
  const { dock, shipyard } = result;
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-slate-900">
            {shipyard.name} <span className="font-normal text-slate-500">· {shipyard.port.name}</span>
          </h2>
          <p className="flex items-center gap-1.5 text-sm text-slate-700">
            <CalendarRange className="size-4 text-slate-400" aria-hidden />
            {formatPeriod(result.startDate, result.endDate)}
          </p>
          <p className="flex items-center gap-1.5 text-sm text-slate-600">
            <Ruler className="size-4 text-slate-400" aria-hidden />
            {dock.name} ({DOCK_TYPES[dock.type]}) : jusqu'à {formatMeters(dock.maxLengthM)} × {formatMeters(dock.maxBeamM)}, tirant d'eau{" "}
            {formatMeters(dock.maxDraftM)}
          </p>
          <p className="flex items-center gap-1.5 text-xs text-emerald-700">
            <Check className="size-3.5" aria-hidden />
            Compatible avec {vessel.name} ({formatMeters(vessel.lengthM)} × {formatMeters(vessel.beamM)} × {formatMeters(vessel.draftM)})
          </p>
        </div>
        {result.existingBookingId ? (
          <div className="flex flex-col items-end gap-2">
            <Badge tone="amber">Demande déjà envoyée</Badge>
            <Link to={`/reservations/${result.existingBookingId}`} className="text-sm font-medium text-brand-600 hover:underline">
              Voir la demande
            </Link>
          </div>
        ) : (
          !requesting && <Button onClick={() => setRequesting(true)}>Demander ce créneau</Button>
        )}
      </div>
      {requesting && <RequestForm result={result} vessel={vessel} onCancel={() => setRequesting(false)} />}
    </Card>
  );
}

function RequestForm({ result, vessel, onCancel }: { result: SearchResult; vessel: Vessel; onCancel: () => void }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [serviceIds, setServiceIds] = useState<string[]>([]);
  const [message, setMessage] = useState("");

  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/bookings", {
          body: { vesselId: vessel.id, slotId: result.slotId, serviceIds, message: message.trim() || undefined },
        }),
      ),
    onSuccess: (booking) => {
      toast.success("Demande envoyée au chantier");
      void queryClient.invalidateQueries();
      navigate(`/reservations/${booking.id}`);
    },
  });
  const toggle = (id: string) => setServiceIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  const total = result.services.filter((s) => serviceIds.includes(s.id)).reduce((sum, s) => sum + (s.indicativePrice ?? 0), 0);
  const servicesError = create.error instanceof ApiError ? create.error.details.serviceIds : undefined;

  return (
    <form
      className="mt-5 space-y-4 border-t border-slate-100 pt-5"
      onSubmit={(event) => {
        event.preventDefault();
        create.mutate();
      }}
    >
      <fieldset>
        <legend className="text-sm font-medium text-slate-700">Services souhaités</legend>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {result.services.map((service) => (
            <label key={service.id} className="flex cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm ring-1 ring-slate-200 has-checked:bg-brand-50 has-checked:ring-brand-500">
              <span className="flex items-center gap-2">
                <input type="checkbox" className="size-4 accent-brand-600" checked={serviceIds.includes(service.id)} onChange={() => toggle(service.id)} />
                {service.name}
              </span>
              {service.indicativePrice !== undefined && <span className="text-slate-500">{formatEuros(service.indicativePrice)}</span>}
            </label>
          ))}
        </div>
        {servicesError && <p className="mt-1 text-xs text-rose-600">{servicesError}</p>}
      </fieldset>
      <Field label="Message au chantier (facultatif)">
        <textarea className={inputClass} rows={2} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Date d'arrivée, contraintes, contact à bord…" />
      </Field>
      {create.error && !servicesError && <ErrorNotice error={create.error} />}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600">{total > 0 ? `Total indicatif : ${formatEuros(total)} HT` : "Sélectionnez au moins un service."}</p>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={onCancel}>
            Annuler
          </Button>
          <Button type="submit" loading={create.isPending} disabled={serviceIds.length === 0}>
            Envoyer la demande
          </Button>
        </div>
      </div>
    </form>
  );
}
