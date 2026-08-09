import type { SyncStatus } from "../api/types";

const STORAGE_KEY = "brewingos.e2a6.mutationQueue.v1";

export type QueuedMutation = {
  id: string;
  operation: string;
  method: "POST";
  path: string;
  payload: Record<string, unknown>;
  client_submission_id: string;
  expected_session_version: number | null;
  session_id: string | null;
  created_at: string;
  status: SyncStatus;
  last_error: string | null;
  error_code: string | null;
  attempts: number;
};

function readStore(): QueuedMutation[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as QueuedMutation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeStore(items: QueuedMutation[]): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

export function listQueuedMutations(): QueuedMutation[] {
  return readStore();
}

export function enqueueMutation(
  input: Omit<QueuedMutation, "created_at" | "status" | "last_error" | "error_code" | "attempts"> & {
    status?: SyncStatus;
  },
): QueuedMutation {
  const row: QueuedMutation = {
    ...input,
    created_at: new Date().toISOString(),
    status: input.status ?? "UNSYNCED",
    last_error: null,
    error_code: null,
    attempts: 0,
  };
  const all = readStore();
  all.push(row);
  writeStore(all);
  return row;
}

export function updateMutation(
  id: string,
  patch: Partial<QueuedMutation>,
): QueuedMutation | null {
  const all = readStore();
  const idx = all.findIndex((m) => m.id === id);
  if (idx < 0) return null;
  all[idx] = { ...all[idx], ...patch };
  writeStore(all);
  return all[idx];
}

export function removeMutation(id: string): void {
  writeStore(readStore().filter((m) => m.id !== id));
}

export function pendingMutations(): QueuedMutation[] {
  return readStore().filter((m) =>
    ["UNSYNCED", "SYNCING", "SYNC_FAILED"].includes(m.status),
  );
}

export function overallSyncStatus(items: QueuedMutation[] = readStore()): SyncStatus {
  if (items.some((m) => m.status === "CONFLICT" || m.status === "REJECTED")) {
    return items.some((m) => m.status === "CONFLICT") ? "CONFLICT" : "REJECTED";
  }
  if (items.some((m) => m.status === "SYNCING")) return "SYNCING";
  if (items.some((m) => m.status === "SYNC_FAILED" || m.status === "UNSYNCED")) {
    return items.some((m) => m.status === "SYNC_FAILED") ? "SYNC_FAILED" : "UNSYNCED";
  }
  return "SYNCED";
}

/** Test helper — clear durable queue. */
export function clearMutationQueue(): void {
  writeStore([]);
}
