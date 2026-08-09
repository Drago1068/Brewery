import { API_URL, ApiError, parseApiError } from "../api/http";
import { newClientSubmissionId } from "../lib/ids";
import {
  enqueueMutation,
  pendingMutations,
  removeMutation,
  updateMutation,
  type QueuedMutation,
} from "./mutationQueue";

export type MutateResult<T> =
  | { ok: true; data: T; fromQueue?: boolean }
  | { ok: false; queued: QueuedMutation; error: Error }
  | { ok: false; conflict: true; error: ApiError; queued?: QueuedMutation };

/**
 * Execute a mutating command. Generates client_submission_id before send.
 * On network failure, persists UNSYNCED queue entry with the same submission id.
 * On OCC/idempotency conflict, marks CONFLICT and does not mint a new submission id.
 */
export async function mutateWithQueue<T>(opts: {
  operation: string;
  path: string;
  buildPayload: (clientSubmissionId: string) => Record<string, unknown>;
  expected_session_version?: number | null;
  session_id?: string | null;
  client_submission_id?: string;
}): Promise<MutateResult<T>> {
  const client_submission_id = opts.client_submission_id ?? newClientSubmissionId(opts.operation);
  const payload = opts.buildPayload(client_submission_id);
  const queueId = newClientSubmissionId("q");

  try {
    const res = await fetch(`${API_URL}${opts.path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await parseApiError(res);
      if (err.code === "CONCURRENCY_CONFLICT" || err.code === "IDEMPOTENCY_CONFLICT") {
        const queued = enqueueMutation({
          id: queueId,
          operation: opts.operation,
          method: "POST",
          path: opts.path,
          payload,
          client_submission_id,
          expected_session_version: opts.expected_session_version ?? null,
          session_id: opts.session_id ?? null,
          status: "CONFLICT",
        });
        updateMutation(queued.id, {
          last_error: err.message,
          error_code: err.code ?? null,
        });
        return { ok: false, conflict: true, error: err, queued };
      }
      // Domain rejection — not silently retried as success
      if (res.status === 409 || res.status === 422) {
        const queued = enqueueMutation({
          id: queueId,
          operation: opts.operation,
          method: "POST",
          path: opts.path,
          payload,
          client_submission_id,
          expected_session_version: opts.expected_session_version ?? null,
          session_id: opts.session_id ?? null,
          status: "REJECTED",
        });
        updateMutation(queued.id, {
          last_error: err.message,
          error_code: err.code ?? null,
        });
        return { ok: false, conflict: true, error: err, queued };
      }
      throw err;
    }
    const data = (await res.json()) as T;
    return { ok: true, data };
  } catch (e) {
    const error = e instanceof Error ? e : new Error(String(e));
    // Network / unexpected — queue for replay with SAME client_submission_id
    if (e instanceof ApiError && (e.status === 409 || e.status === 422)) {
      throw e;
    }
    const queued = enqueueMutation({
      id: queueId,
      operation: opts.operation,
      method: "POST",
      path: opts.path,
      payload,
      client_submission_id,
      expected_session_version: opts.expected_session_version ?? null,
      session_id: opts.session_id ?? null,
      status: "UNSYNCED",
    });
    updateMutation(queued.id, { last_error: error.message });
    return { ok: false, queued, error };
  }
}

/** Replay pending UNSYNCED/SYNC_FAILED mutations. Exact replay keeps original submission id. */
export async function replayPendingMutations(): Promise<{
  synced: number;
  failed: number;
  conflicts: number;
}> {
  let synced = 0;
  let failed = 0;
  let conflicts = 0;
  for (const item of pendingMutations()) {
    updateMutation(item.id, { status: "SYNCING", attempts: item.attempts + 1 });
    try {
      const res = await fetch(`${API_URL}${item.path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item.payload),
      });
      if (res.ok) {
        removeMutation(item.id);
        synced += 1;
        continue;
      }
      const err = await parseApiError(res);
      if (err.code === "CONCURRENCY_CONFLICT" || err.code === "IDEMPOTENCY_CONFLICT") {
        updateMutation(item.id, {
          status: "CONFLICT",
          last_error: err.message,
          error_code: err.code ?? null,
        });
        conflicts += 1;
        continue;
      }
      if (res.status === 409 || res.status === 422) {
        updateMutation(item.id, {
          status: "REJECTED",
          last_error: err.message,
          error_code: err.code ?? null,
        });
        conflicts += 1;
        continue;
      }
      updateMutation(item.id, {
        status: "SYNC_FAILED",
        last_error: err.message,
        error_code: err.code ?? null,
      });
      failed += 1;
    } catch (e) {
      updateMutation(item.id, {
        status: "SYNC_FAILED",
        last_error: e instanceof Error ? e.message : String(e),
      });
      failed += 1;
    }
  }
  return { synced, failed, conflicts };
}
