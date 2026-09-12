import net from "node:net";
import { APPS } from "@anti-sovereign/design-system/apps-registry";

export interface HealthStatus {
  online: boolean;
  name: string;
  status: "Healthy" | "Port Open" | "Offline";
}

async function probeWhoami(port: number): Promise<HealthStatus | null> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 800);
    let res: Response;
    try {
      res = await fetch(`http://127.0.0.1:${port}/api/whoami`, { signal: controller.signal });
    } finally {
      clearTimeout(timeout);
    }
    if (!res.ok) return null;
    const data: unknown = await res.json();
    if (!data || typeof data !== "object" || typeof (data as { name?: unknown }).name !== "string") {
      return null;
    }
    return { online: true, name: (data as { name: string }).name, status: "Healthy" };
  } catch {
    return null;
  }
}

function probeTcp(port: number): Promise<HealthStatus> {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    const finish = (online: boolean) => {
      socket.destroy();
      resolve(
        online
          ? { online: true, name: "Active Port", status: "Port Open" }
          : { online: false, name: "-", status: "Offline" },
      );
    };
    socket.setTimeout(500);
    socket.once("connect", () => finish(true));
    socket.once("timeout", () => finish(false));
    socket.once("error", () => finish(false));
    socket.connect(port, "127.0.0.1");
  });
}

export async function checkAppHealth(port: number): Promise<HealthStatus> {
  const whoami = await probeWhoami(port);
  if (whoami) return whoami;
  return probeTcp(port);
}

export async function checkAllApps(): Promise<Record<string, HealthStatus>> {
  const entries = await Promise.all(APPS.map(async (app) => [app.id, await checkAppHealth(app.port)] as const));
  return Object.fromEntries(entries);
}
