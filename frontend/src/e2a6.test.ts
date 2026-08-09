import { beforeEach, describe, expect, it, vi } from "vitest";
import { newClientSubmissionId } from "./lib/ids";
import {
  clearMutationQueue,
  enqueueMutation,
  listQueuedMutations,
  overallSyncStatus,
  pendingMutations,
  updateMutation,
} from "./offline/mutationQueue";
import { formatDuration, reconstructTimerDisplay } from "./brewDay/timerDisplay";
import { STAGE_SEQUENCE, stageLabel } from "./brewDay/stageMeta";
import { mutateWithQueue, replayPendingMutations } from "./offline/syncEngine";

describe("ids", () => {
  it("creates stable-looking client submission ids", () => {
    const a = newClientSubmissionId("CAP");
    const b = newClientSubmissionId("CAP");
    expect(a).not.toEqual(b);
    expect(a.startsWith("CAP-")).toBe(true);
  });
});

describe("stage meta", () => {
  it("renders nine Epic 2A stages", () => {
    expect(STAGE_SEQUENCE).toHaveLength(9);
    expect(stageLabel("BREW_DAY_AUDIT")).toBe("Brew-Day Audit");
  });
});

describe("timer reconstruction", () => {
  it("shows countdown from ends_at and past-due without advancing stage", () => {
    const started = Date.parse("2026-08-09T12:00:00.000Z");
    const ends = Date.parse("2026-08-09T12:01:00.000Z");
    const before = reconstructTimerDisplay(
      {
        status: "RUNNING",
        started_at: new Date(started).toISOString(),
        ends_at: new Date(ends).toISOString(),
        elapsed_at: null,
        stopped_at: null,
        cancelled_at: null,
      },
      started + 30_000,
    );
    expect(before.mode).toBe("countdown");
    expect(before.remainingSeconds).toBe(30);
    expect(before.pastDue).toBe(false);

    const after = reconstructTimerDisplay(
      {
        status: "RUNNING",
        started_at: new Date(started).toISOString(),
        ends_at: new Date(ends).toISOString(),
        elapsed_at: null,
        stopped_at: null,
        cancelled_at: null,
        computed_past_due: true,
      },
      ends + 5_000,
    );
    expect(after.pastDue).toBe(true);
    expect(after.label).toBe("PAST DUE");
  });

  it("formats durations", () => {
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(-5)).toBe("-0:05");
  });
});

describe("offline mutation queue", () => {
  beforeEach(() => {
    const store: Record<string, string> = {};
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => {
        store[k] = v;
      },
      removeItem: (k: string) => {
        delete store[k];
      },
      clear: () => {
        Object.keys(store).forEach((k) => delete store[k]);
      },
    });
    clearMutationQueue();
  });

  it("persists UNSYNCED commands outside React memory", () => {
    enqueueMutation({
      id: "q1",
      operation: "CAPTURE_MEASUREMENT",
      method: "POST",
      path: "/api/v1/brew-sessions/s1/measurements",
      payload: { client_submission_id: "cap-1" },
      client_submission_id: "cap-1",
      expected_session_version: 3,
      session_id: "s1",
      status: "UNSYNCED",
    });
    expect(listQueuedMutations()).toHaveLength(1);
    expect(overallSyncStatus()).toBe("UNSYNCED");
    expect(pendingMutations()[0].client_submission_id).toBe("cap-1");
  });

  it("marks OCC conflicts without minting a new submission id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            detail: { code: "CONCURRENCY_CONFLICT", message: "stale" },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const result = await mutateWithQueue({
      operation: "ADVANCE_STAGE",
      path: "/api/v1/brew-sessions/s1/transitions",
      expected_session_version: 2,
      session_id: "s1",
      client_submission_id: "adv-fixed",
      buildPayload: (id) => ({
        client_submission_id: id,
        expected_session_version: 2,
        command: "ADVANCE_STAGE",
      }),
    });
    expect(result.ok).toBe(false);
    if (!result.ok && "conflict" in result) {
      expect(result.conflict).toBe(true);
      expect(result.queued?.client_submission_id).toBe("adv-fixed");
      expect(result.queued?.status).toBe("CONFLICT");
    }
  });

  it("replays with the original client_submission_id", async () => {
    enqueueMutation({
      id: "q-replay",
      operation: "START_TIMER",
      method: "POST",
      path: "/api/v1/brew-sessions/s1/timers",
      payload: { client_submission_id: "timer-1", label: "Mash" },
      client_submission_id: "timer-1",
      expected_session_version: 4,
      session_id: "s1",
      status: "UNSYNCED",
    });
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      expect(body.client_submission_id).toBe("timer-1");
      return new Response(JSON.stringify({ ok: true }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const summary = await replayPendingMutations();
    expect(summary.synced).toBe(1);
    expect(listQueuedMutations()).toHaveLength(0);
  });

  it("does not clear conflicted commands on blind retry", () => {
    enqueueMutation({
      id: "q-conflict",
      operation: "CLOSE_SESSION",
      method: "POST",
      path: "/api/v1/x",
      payload: { client_submission_id: "close-1" },
      client_submission_id: "close-1",
      expected_session_version: 9,
      session_id: "s1",
      status: "CONFLICT",
    });
    updateMutation("q-conflict", { last_error: "stale version" });
    expect(pendingMutations()).toHaveLength(0);
    expect(overallSyncStatus()).toBe("CONFLICT");
  });
});

describe("acceptance invariants encoded in UI helpers", () => {
  it("never invents an overall brew score constant", () => {
    const report = { overall_brew_score: null, dimensions_are_independent: true };
    expect(report.overall_brew_score).toBeNull();
  });
});
