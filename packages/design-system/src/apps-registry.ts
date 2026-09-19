export interface AppRegistryEntry {
  id: string;
  name: string;
  port: number;
  category: "Registry" | "Attestation" | "CreativeOS";
  accent: string;
  description: string;
}

/**
 * Canonical list of every in-scope app, its port, and its one accent color.
 * Consumed by the Gateway's dashboard/health-check and by each app's own
 * globals.css when it sets --accent. Keep this the single source of truth
 * for ports instead of duplicating numbers per app.
 */
export const APPS: AppRegistryEntry[] = [
  {
    id: "canonlock",
    name: "Canonlock",
    port: 5501,
    category: "Registry",
    accent: "#F59E0B",
    description: "SHA-256 registry: Merkle inclusion proofs, sealed certificates, RFC-3161 timestamps.",
  },
  {
    id: "veridact",
    name: "Veridact",
    port: 5502,
    category: "Attestation",
    accent: "#7C3AED",
    description: "Device-bound signing for live captures, plus LSB watermarking.",
  },
  {
    id: "story-atlas",
    name: "Story Atlas",
    port: 5503,
    category: "CreativeOS",
    accent: "#C1121F",
    description: "Worldbuilding and canon engine",
  },
  {
    id: "framevault",
    name: "FrameVault",
    port: 5504,
    category: "CreativeOS",
    accent: "#E5482D",
    description: "Dailies and asset vault; ecosystem identity and reputation hub",
  },
  {
    id: "filmcrew",
    name: "FilmCrew",
    port: 5505,
    category: "CreativeOS",
    accent: "#0891B2",
    description: "Crew and project collaboration",
  },
  {
    id: "rightsforge",
    name: "RightsForge",
    port: 5506,
    category: "CreativeOS",
    accent: "#65A30D",
    description: "Rights and licensing workflows",
  },
  {
    id: "creatorstack",
    name: "CreatorStack",
    port: 5507,
    category: "CreativeOS",
    accent: "#DB2777",
    description: "Creator tooling and challenges",
  },
  {
    id: "studio",
    name: "OTT Studio",
    port: 5508,
    category: "CreativeOS",
    accent: "#4F46E5",
    description: "Production workspace",
  },
];
