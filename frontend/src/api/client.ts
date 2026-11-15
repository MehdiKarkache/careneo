import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

// Les types viennent du contrat docs/openapi.yaml (npm run api:types) : le front et l'API
// partagent la même source de vérité.
export type Schemas = components["schemas"];
export type Role = Schemas["Role"];
export type BookingStatus = Schemas["BookingStatus"];
export type Booking = Schemas["Booking"];
export type BookingDetail = Schemas["BookingDetail"];
export type Vessel = Schemas["Vessel"];
export type VesselInput = Schemas["VesselInput"];
export type VesselType = Schemas["VesselType"];
export type Port = Schemas["Port"];
export type Dock = Schemas["Dock"];
export type Service = Schemas["Service"];
export type SearchResult = Schemas["SearchResult"];
export type Me = Schemas["Me"];

export const api = createClient<paths>();

/** Erreur au format du contrat : {"error": {"code", "message", "details"}}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, string>;

  constructor(status: number, code: string, message: string, details: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type ErrorBody = { error?: { code?: string; message?: string; details?: Record<string, unknown> } };

/** Renvoie les données d'un appel typé, ou lève une ApiError lisible. */
export async function call<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: Awaited<typeof request>;
  try {
    result = await request;
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Serveur injoignable, vérifiez votre connexion");
  }
  const { data, error, response } = result;
  if (!response.ok) {
    const body = (error ?? {}) as ErrorBody;
    const details = Object.fromEntries(
      Object.entries(body.error?.details ?? {}).map(([field, message]) => [field, String(message)]),
    );
    throw new ApiError(
      response.status,
      body.error?.code ?? "INTERNAL_ERROR",
      body.error?.message ?? "Erreur inattendue",
      details,
    );
  }
  return data as T;
}
