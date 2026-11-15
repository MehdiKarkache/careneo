import type { BookingStatus, Role, VesselType } from "../api/client";

export type Tone = "amber" | "emerald" | "rose" | "slate" | "sky" | "indigo";

export const BOOKING_STATUS: Record<BookingStatus, { label: string; tone: Tone }> = {
  PENDING: { label: "En attente", tone: "amber" },
  ACCEPTED: { label: "Acceptée", tone: "emerald" },
  REJECTED: { label: "Refusée", tone: "rose" },
  CANCELLED: { label: "Annulée", tone: "slate" },
  EXPIRED: { label: "Expirée", tone: "slate" },
  COMPLETED: { label: "Terminée", tone: "sky" },
};

export const SLOT_STATUS: Record<"OPEN" | "BOOKED" | "CLOSED", { label: string; tone: Tone }> = {
  OPEN: { label: "Ouvert", tone: "emerald" },
  BOOKED: { label: "Attribué", tone: "indigo" },
  CLOSED: { label: "Fermé", tone: "slate" },
};

export const ROLES: Record<Role, string> = {
  OWNER: "Armateur",
  YARD: "Chantier naval",
  ADMIN: "Administrateur",
};

export const VESSEL_TYPES: Record<VesselType, string> = {
  FERRY: "Ferry",
  CONTAINER_SHIP: "Porte-conteneurs",
  TANKER: "Navire-citerne",
  RO_RO: "Roulier",
  OTHER: "Autre",
};

export const DOCK_TYPES: Record<"DRY_DOCK" | "FLOATING_DOCK" | "SHIPLIFT", string> = {
  DRY_DOCK: "Forme de radoub",
  FLOATING_DOCK: "Dock flottant",
  SHIPLIFT: "Élévateur à navires",
};

export const SERVICE_CATEGORIES: Record<string, string> = {
  HULL_CLEANING: "Nettoyage de coque",
  ANTIFOULING: "Antifouling",
  ANODES: "Anodes",
  PROPELLER: "Hélice",
  INSPECTION: "Inspection",
  VALVES: "Vannes",
  PAINTING: "Peinture",
  OTHER: "Autre",
};

/** Une date « AAAA-MM-JJ » du contrat est un jour calendaire : pas de conversion de fuseau. */
export function parseDay(day: string): Date {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year, month - 1, date);
}

export function toDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function addDays(date: Date, days: number): Date {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

export function formatDay(day: string): string {
  return parseDay(day).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
}

export function dayCount(start: string, end: string): number {
  return Math.round((parseDay(end).getTime() - parseDay(start).getTime()) / 86_400_000) + 1;
}

export function formatPeriod(start: string, end: string): string {
  return `${formatDay(start)} → ${formatDay(end)} · ${dayCount(start, end)} jours`;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
}

export function formatEuros(amount: number): string {
  return amount.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

export function formatMeters(value: number): string {
  return `${value.toLocaleString("fr-FR")} m`;
}

/** Accepte la virgule décimale française. */
export function parseNumber(value: string): number | undefined {
  const parsed = Number(value.replace(",", ".").trim());
  return value.trim() === "" || Number.isNaN(parsed) ? undefined : parsed;
}
