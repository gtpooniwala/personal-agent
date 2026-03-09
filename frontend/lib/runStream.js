import { RUNTIME_API_BASE } from "@/lib/api";

export const DEFAULT_RUN_STREAM_INACTIVITY_TIMEOUT_MS = 60_000;

export function subscribeToRunStream(
  runId,
  {
    onStateUpdate,
    onComplete,
    onFallback,
    inactivityTimeoutMs = DEFAULT_RUN_STREAM_INACTIVITY_TIMEOUT_MS,
  },
) {
  if (typeof EventSource === "undefined") {
    onFallback();
    return () => {};
  }

  let closed = false;
  let es;
  let watchdogTimer = null;

  const clearWatchdog = () => {
    if (watchdogTimer !== null) {
      clearTimeout(watchdogTimer);
      watchdogTimer = null;
    }
  };

  const triggerFallback = () => {
    if (closed) {
      return;
    }
    closed = true;
    clearWatchdog();
    es.close();
    onFallback();
  };

  const resetWatchdog = () => {
    clearWatchdog();
    watchdogTimer = setTimeout(() => {
      triggerFallback();
    }, inactivityTimeoutMs);
  };

  try {
    es = new EventSource(`${RUNTIME_API_BASE}/runs/${runId}/stream`);
  } catch {
    onFallback();
    return () => {};
  }
  resetWatchdog();

  es.addEventListener("run_event", (event) => {
    if (closed) return;
    resetWatchdog();
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      triggerFallback();
      return;
    }
    onStateUpdate({ type: "run_event", event: normalizeRunEventData(data) });
  });

  es.addEventListener("run_complete", (event) => {
    if (closed) return;
    resetWatchdog();
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      triggerFallback();
      return;
    }
    closed = true;
    clearWatchdog();
    es.close();
    onStateUpdate({ type: "run_complete", status: data.status, error: data.error ?? null });
    onComplete(data);
  });

  es.addEventListener("heartbeat", () => {
    if (closed) return;
    resetWatchdog();
  });

  es.onerror = () => {
    triggerFallback();
  };

  return () => {
    if (closed) {
      return;
    }
    closed = true;
    clearWatchdog();
    es.close();
  };
}

function normalizeRunEventData(data) {
  return {
    event_id: data.event_id,
    type: data.event_type,
    status: data.status,
    message: data.payload?.message ?? null,
    tool: data.payload?.tool ?? null,
    metadata: data.payload?.metadata ?? null,
    created_at: data.timestamp,
  };
}
