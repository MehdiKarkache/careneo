import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Factory, Plus, Wrench } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { ApiError, api, call, type Dock } from "../../api/client";
import { Button, Card, EmptyState, ErrorNotice, Field, PageHeader, SlotStatusBadge, Spinner, inputClass } from "../../components/ui";
import { DOCK_TYPES, SERVICE_CATEGORIES, addDays, formatEuros, formatMeters, formatPeriod, parseNumber, toDay } from "../../lib/format";

export function ShipyardPage() {
  const shipyards = useQuery({ queryKey: ["shipyards"], queryFn: () => call(api.GET("/api/shipyards")) });
  if (shipyards.isPending) return <Spinner />;
  if (shipyards.isError) return <ErrorNotice error={shipyards.error} />;
  return (
    <>
      <PageHeader title="Postes et créneaux" description="Ouvrez des créneaux de disponibilité et gérez les services proposés aux armateurs." />
      {shipyards.data.length === 0 ? (
        <EmptyState icon={Factory} title="Aucun chantier rattaché à votre entreprise" />
      ) : (
        <div className="space-y-10">
          {shipyards.data.map((shipyard) => (
            <ShipyardSection key={shipyard.id} id={shipyard.id} />
          ))}
        </div>
      )}
    </>
  );
}

function ShipyardSection({ id }: { id: string }) {
  const shipyard = useQuery({
    queryKey: ["shipyard", id],
    queryFn: () => call(api.GET("/api/shipyards/{id}", { params: { path: { id } } })),
  });
  if (shipyard.isPending) return <Spinner />;
  if (shipyard.isError) return <ErrorNotice error={shipyard.error} />;
  const { name, port, description, docks, services } = shipyard.data;
  return (
    <section>
      <h2 className="text-lg font-semibold text-slate-900">
        {name} <span className="font-normal text-slate-500">· {port.name}</span>
      </h2>
      {description && <p className="text-sm text-slate-500">{description}</p>}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {docks.map((dock) => (
          <DockCard key={dock.id} dock={dock} />
        ))}
      </div>
      <Card className="mt-4 p-5">
        <h3 className="flex items-center gap-2 font-semibold text-slate-900">
          <Wrench className="size-4 text-slate-400" aria-hidden />
          Services proposés
        </h3>
        <ul className="mt-3 divide-y divide-slate-100 text-sm">
          {services.map((service) => (
            <li key={service.id} className="flex justify-between gap-4 py-2">
              <span>
                {service.name} <span className="text-xs text-slate-400">{SERVICE_CATEGORIES[service.category] ?? service.category}</span>
              </span>
              <span className="tabular-nums text-slate-600">{service.indicativePrice !== undefined ? formatEuros(service.indicativePrice) : "Sur devis"}</span>
            </li>
          ))}
        </ul>
        <ServiceForm shipyardId={id} />
      </Card>
    </section>
  );
}

function DockCard({ dock }: { dock: Dock }) {
  const slots = useQuery({
    queryKey: ["slots", dock.id],
    queryFn: () => call(api.GET("/api/docks/{id}/slots", { params: { path: { id: dock.id } } })),
  });
  return (
    <Card className="p-5">
      <h3 className="font-semibold text-slate-900">{dock.name}</h3>
      <p className="text-xs text-slate-500">
        {DOCK_TYPES[dock.type]} · jusqu'à {formatMeters(dock.maxLengthM)} × {formatMeters(dock.maxBeamM)}, tirant d'eau {formatMeters(dock.maxDraftM)}
      </p>
      {slots.isPending ? (
        <Spinner />
      ) : slots.isError ? (
        <ErrorNotice error={slots.error} />
      ) : (
        <ul className="mt-3 max-h-56 divide-y divide-slate-100 overflow-y-auto text-sm">
          {slots.data.length === 0 && <li className="py-2 text-slate-500">Aucun créneau à venir.</li>}
          {slots.data.map((slot) => (
            <li key={slot.id} className="flex items-center justify-between gap-3 py-2">
              <span className="text-slate-700">{formatPeriod(slot.startDate, slot.endDate)}</span>
              <SlotStatusBadge status={slot.status} />
            </li>
          ))}
        </ul>
      )}
      <SlotForm dockId={dock.id} />
    </Card>
  );
}

function SlotForm({ dockId }: { dockId: string }) {
  const queryClient = useQueryClient();
  const tomorrow = addDays(new Date(), 1);
  const [startDate, setStartDate] = useState(toDay(addDays(tomorrow, 30)));
  const [endDate, setEndDate] = useState(toDay(addDays(tomorrow, 41)));
  const create = useMutation({
    mutationFn: () => call(api.POST("/api/docks/{id}/slots", { params: { path: { id: dockId } }, body: { startDate, endDate } })),
    onSuccess: () => {
      toast.success("Créneau ouvert");
      void queryClient.invalidateQueries({ queryKey: ["slots", dockId] });
    },
  });
  const errors = create.error instanceof ApiError ? create.error.details : {};
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };
  return (
    <form onSubmit={submit} className="mt-4 border-t border-slate-100 pt-4">
      <div className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
        <Field label="Début" error={errors.startDate}>
          <input type="date" className={inputClass} value={startDate} min={toDay(tomorrow)} onChange={(e) => setStartDate(e.target.value)} required />
        </Field>
        <Field label="Fin" error={errors.endDate}>
          <input type="date" className={inputClass} value={endDate} min={startDate} onChange={(e) => setEndDate(e.target.value)} required />
        </Field>
        <Button type="submit" variant="secondary" loading={create.isPending} title="Ouvrir le créneau">
          <CalendarPlus className="size-4" aria-hidden />
          Ouvrir
        </Button>
      </div>
      {create.error && Object.keys(errors).length === 0 && (
        <div className="mt-2">
          <ErrorNotice error={create.error} />
        </div>
      )}
    </form>
  );
}

function ServiceForm({ shipyardId }: { shipyardId: string }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [category, setCategory] = useState("HULL_CLEANING");
  const [price, setPrice] = useState("");
  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/shipyards/{id}/services", {
          params: { path: { id: shipyardId } },
          body: { name, category, indicativePrice: parseNumber(price) },
        }),
      ),
    onSuccess: (service) => {
      toast.success(`Service « ${service.name} » ajouté`);
      setName("");
      setPrice("");
      void queryClient.invalidateQueries({ queryKey: ["shipyard", shipyardId] });
    },
  });
  const errors = create.error instanceof ApiError ? create.error.details : {};
  return (
    <form
      className="mt-4 grid items-end gap-2 border-t border-slate-100 pt-4 sm:grid-cols-[2fr_1fr_1fr_auto]"
      onSubmit={(event) => {
        event.preventDefault();
        create.mutate();
      }}
    >
      <Field label="Nouveau service" error={errors.name}>
        <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex. : peinture des œuvres mortes" required />
      </Field>
      <Field label="Catégorie" error={errors.category}>
        <select className={inputClass} value={category} onChange={(e) => setCategory(e.target.value)}>
          {Object.entries(SERVICE_CATEGORIES).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Prix indicatif (€ HT)" error={errors.indicativePrice}>
        <input className={inputClass} value={price} onChange={(e) => setPrice(e.target.value)} inputMode="numeric" placeholder="Sur devis" />
      </Field>
      <Button type="submit" variant="secondary" loading={create.isPending}>
        <Plus className="size-4" aria-hidden />
        Ajouter
      </Button>
    </form>
  );
}
