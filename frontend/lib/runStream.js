import { RUNTIME_API_BASE } from "@/lib/api";

export function subscribeToRunStream(runId, { onStateUpdate, onComplete, onFallback }) {
  if (typeof EventSource === "undefined") {
    onFallback();
    return () => {};
  }

  let closed = false;
  const es = new EventSource(`${RUNTIME_API_BASE}/runs/${runId}/stream`);

  es.addEventListener("run_event", (event) => {
    if (closed) return;
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      es.close();
      onFallback();
      return;
    }
    onStateUpdate({ type: "run_event", event: normalizeRunEventData(data) });
  });

  es.addEventListener("run_complete", (event) => {
    if (closed) return;
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      es.close();
      onFallback();
      return;
    }
    closed = true;
    es.close();
    onStateUpdate({ type: "run_complete", status: data.status, error: data.error ?? null });
    onComplete(data);
  });

  es.addEventListener("heartbeat", () => {});

  es.onerror = () => {
    if (closed) return;
    es.close();
    onFallback();
  };

  return () => {
    closed = true;
    es.close();
  };
}

function normalizeRunEventData(data) {
  return {
    event_id: data.event_id,
    event_type: data.event_type,
    status: data.status,
    message: data.payload?.message ?? null,
    tool: data.payload?.tool ?? null,
    metadata: data.payload?.metadata ?? null,
    timestamp: data.timestamp,
  };
}
