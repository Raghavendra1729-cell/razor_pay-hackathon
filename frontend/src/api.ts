import type { Report } from "./types";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export async function runDemoReconciliation(): Promise<Report> {
  const response = await fetch(`${apiUrl}/api/reconcile/demo`, { method: "POST" });
  if (!response.ok) {
    throw new Error("The reconciliation API did not return a report.");
  }
  return response.json() as Promise<Report>;
}
