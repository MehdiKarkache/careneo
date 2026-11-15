import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Ship } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { ApiError, api, call, type Vessel, type VesselType } from "../../api/client";
import { Button, Card, EmptyState, ErrorNotice, Field, PageHeader, Spinner, inputClass } from "../../components/ui";
import { VESSEL_TYPES, formatMeters, parseNumber } from "../../lib/format";

export function VesselsPage() {
  const vessels = useQuery({ queryKey: ["vessels"], queryFn: () => call(api.GET("/api/vessels")) });
  const [editing, setEditing] = useState<Vessel | "new" | null>(null);

  return (
    <>
      <PageHeader
        title="Ma flotte"
        description="Les dimensions servent à ne proposer que les postes compatibles."
        actions={
          editing === null && (
            <Button onClick={() => setEditing("new")}>
              <Plus className="size-4" aria-hidden />
              Ajouter un navire
            </Button>
          )
        }
      />
      {editing !== null && (
        <VesselForm key={editing === "new" ? "new" : editing.id} vessel={editing === "new" ? undefined : editing} onDone={() => setEditing(null)} />
      )}
      {vessels.isPending ? (
        <Spinner />
      ) : vessels.isError ? (
        <ErrorNotice error={vessels.error} />
      ) : vessels.data.length === 0 ? (
        <EmptyState icon={Ship} title="Aucun navire pour l'instant" />
      ) : (
        <Card className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Navire</th>
                <th className="px-4 py-3 font-medium">IMO</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Longueur × largeur × tirant d'eau</th>
                <th className="px-4 py-3 font-medium">Jauge brute</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {vessels.data.map((vessel) => (
                <tr key={vessel.id}>
                  <td className="px-4 py-3 font-medium text-slate-900">{vessel.name}</td>
                  <td className="px-4 py-3 tabular-nums text-slate-600">{vessel.imo}</td>
                  <td className="px-4 py-3 text-slate-600">{VESSEL_TYPES[vessel.type]}</td>
                  <td className="px-4 py-3 tabular-nums text-slate-600">
                    {formatMeters(vessel.lengthM)} × {formatMeters(vessel.beamM)} × {formatMeters(vessel.draftM)}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-slate-600">{vessel.grossTonnage?.toLocaleString("fr-FR") ?? "—"}</td>
                  <td className="px-4 py-3 text-right">
                    <Button variant="ghost" onClick={() => setEditing(vessel)} aria-label={`Modifier ${vessel.name}`}>
                      <Pencil className="size-4" aria-hidden />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}

function VesselForm({ vessel, onDone }: { vessel?: Vessel; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [values, setValues] = useState({
    name: vessel?.name ?? "",
    imo: vessel?.imo ?? "",
    type: vessel?.type ?? ("FERRY" as VesselType),
    lengthM: vessel ? String(vessel.lengthM) : "",
    beamM: vessel ? String(vessel.beamM) : "",
    draftM: vessel ? String(vessel.draftM) : "",
    grossTonnage: vessel?.grossTonnage !== undefined ? String(vessel.grossTonnage) : "",
  });
  const set = (field: keyof typeof values) => (value: string) => setValues((current) => ({ ...current, [field]: value }));

  const save = useMutation({
    mutationFn: () => {
      const dimensions = {
        name: values.name,
        type: values.type,
        lengthM: parseNumber(values.lengthM) as number,
        beamM: parseNumber(values.beamM) as number,
        draftM: parseNumber(values.draftM) as number,
        grossTonnage: parseNumber(values.grossTonnage),
      };
      return vessel
        ? call(api.PATCH("/api/vessels/{id}", { params: { path: { id: vessel.id } }, body: dimensions }))
        : call(api.POST("/api/vessels", { body: { ...dimensions, imo: values.imo } }));
    },
    onSuccess: (saved) => {
      toast.success(vessel ? `${saved.name} mis à jour` : `${saved.name} ajouté à votre flotte`);
      void queryClient.invalidateQueries({ queryKey: ["vessels"] });
      onDone();
    },
  });
  const errors = save.error instanceof ApiError ? save.error.details : {};
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  const input = (field: keyof typeof values, props: Record<string, unknown> = {}) => (
    <input className={inputClass} value={values[field]} onChange={(e) => set(field)(e.target.value)} aria-invalid={Boolean(errors[field])} {...props} />
  );

  return (
    <Card className="mb-6 p-5">
      <h2 className="mb-4 font-semibold text-slate-900">{vessel ? `Modifier ${vessel.name}` : "Nouveau navire"}</h2>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Nom" error={errors.name} className="lg:col-span-2">
          {input("name", { required: true })}
        </Field>
        <Field label="Numéro IMO" error={errors.imo} hint={vessel ? "Identifiant non modifiable" : "7 chiffres, clé de contrôle vérifiée"}>
          {input("imo", { required: true, disabled: Boolean(vessel), inputMode: "numeric", placeholder: "9421001" })}
        </Field>
        <Field label="Type" error={errors.type}>
          <select className={inputClass} value={values.type} onChange={(e) => set("type")(e.target.value)}>
            {Object.entries(VESSEL_TYPES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Longueur hors-tout (m)" error={errors.lengthM}>
          {input("lengthM", { required: true, inputMode: "decimal" })}
        </Field>
        <Field label="Largeur (m)" error={errors.beamM}>
          {input("beamM", { required: true, inputMode: "decimal" })}
        </Field>
        <Field label="Tirant d'eau (m)" error={errors.draftM}>
          {input("draftM", { required: true, inputMode: "decimal" })}
        </Field>
        <Field label="Jauge brute (facultatif)" error={errors.grossTonnage}>
          {input("grossTonnage", { inputMode: "numeric" })}
        </Field>
        {save.error && Object.keys(errors).length === 0 && (
          <div className="sm:col-span-2 lg:col-span-4">
            <ErrorNotice error={save.error} />
          </div>
        )}
        <div className="flex gap-2 sm:col-span-2 lg:col-span-4">
          <Button type="submit" loading={save.isPending}>
            {vessel ? "Enregistrer" : "Ajouter le navire"}
          </Button>
          <Button variant="secondary" onClick={onDone}>
            Annuler
          </Button>
        </div>
      </form>
    </Card>
  );
}
