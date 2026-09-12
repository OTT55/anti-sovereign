import { z } from "zod";

/**
 * Typed client for FrameVault's cross-app identity + reputation surface.
 * Every other CreativeOS app (Story Atlas, FilmCrew, RightsForge,
 * CreatorStack, OTT Studio) delegates login to FrameVault's /api/authenticate
 * and reports completed transactions to /api/credit — mirroring the original
 * Flask ecosystem's pattern, but through one typed SDK instead of five
 * hand-rolled fetch calls. FrameVault remains the only app with a local
 * password store; every caller here forwards credentials once and never
 * persists them.
 */

const identitySchema = z.object({
  handle: z.string(),
  displayName: z.string(),
  verified: z.boolean(),
});

export type Identity = z.infer<typeof identitySchema>;

const authenticateResponseSchema = z.union([
  z.object({ ok: z.literal(true), identity: identitySchema }),
  z.object({ ok: z.literal(false), error: z.string() }),
]);

const creditResponseSchema = z.union([
  z.object({ ok: z.literal(true), eventId: z.string() }),
  z.object({ ok: z.literal(false), error: z.string() }),
]);

export interface CreditEvent {
  /** Handle of the person earning reputation/funds for this event. */
  handle: string;
  /** Machine-readable kind, e.g. "hire.completed", "canon.published". */
  kind: string;
  /** Relative weight of this event toward reputation ranking. */
  weight: number;
  /** Which app/service reported this event, e.g. "filmcrew". */
  source: string;
  /** Amount in integer pence, if a real payment was involved. */
  amountPence?: number;
  /** The paying counterparty's handle, if this was a paid transaction. */
  payerHandle?: string;
  /** Optional public review left alongside the credit. */
  review?: { rating: number; body: string };
}

export interface FrameClientConfig {
  baseUrl: string;
  serviceKey: string;
}

export class FrameClient {
  constructor(private readonly config: FrameClientConfig) {}

  async authenticate(handle: string, password: string): Promise<Identity> {
    const res = await fetch(`${this.config.baseUrl}/api/authenticate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ handle, password }),
    });
    const parsed = authenticateResponseSchema.parse(await res.json());
    if (!parsed.ok) {
      throw new Error(parsed.error);
    }
    return parsed.identity;
  }

  async credit(event: CreditEvent): Promise<string> {
    const res = await fetch(`${this.config.baseUrl}/api/credit`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-service-key": this.config.serviceKey,
      },
      body: JSON.stringify(event),
    });
    const parsed = creditResponseSchema.parse(await res.json());
    if (!parsed.ok) {
      throw new Error(parsed.error);
    }
    return parsed.eventId;
  }
}
