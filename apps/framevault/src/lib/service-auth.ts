import { timingSafeEqual } from "node:crypto";
import { getServiceKey } from "./secrets";

export function isValidServiceKey(presented: string | null): boolean {
  if (!presented) return false;
  const expected = Buffer.from(getServiceKey());
  const actual = Buffer.from(presented);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}
