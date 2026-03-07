"use client";

import { useCallback, useEffect, useState } from "react";
import WorkspaceViewTabs from "@/components/WorkspaceViewTabs";
import { apiCall } from "@/lib/api";
import { formatRelativeTime, formatRunStatusLabel } from "@/lib/formatters";

const REFRESH_INTERVAL_MS = 15000;

function formatWholeNumber(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function formatDecimal(value, suffix = "") {
  if (value === null || value === undefined) {
    return "—";
  }

  return `${new Intl.NumberFormat("en-US", {
    minimumFractionDigits: value % 1 === 0 ? 0 : 1,
    maximumFractionDigits: 1,
  }).format(value)}${suffix}`;
}

function MetricCard({ label, value, hint }) {
  return (
    <article className="dashboard-card">
      <p className="dashboard-label">{label}</p>
      <h3>{value}</h3>
      <p className="dashboard-hint">{hint}</p>
    </article>
  );
}

function KeyValueList({ items, emptyLabel }) {
  if (!items.length) {
    return <p className="dashboard-empty">{emptyLabel}</p>;
  }

  return (
    <div className="metrics-list">
      {items.map(([label, value]) => (
        <div key={label} className="metrics-list-row">
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}

export default function MetricsDashboard({ currentConversationId }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadSummary = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }

    try {
      const payload = await apiCall("/observability/summary");
      setSummary(payload);
      setError("");
    } catch {
      setError("Failed to load metrics.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadSummary();

    const intervalId = window.setInterval(() => {
      void loadSummary({ silent: true });
    }, REFRESH_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [loadSummary]);

  const totals = summary?.totals || {};
  const runtime = summary?.runtime || {};
  const orchestration = summary?.orchestration || {};
  const api = summary?.api || {};
  const runStatusCounts = Object.entries(summary?.run_status_counts || {}).sort(
    (left, right) => right[1] - left[1],
  );
  const toolUsage = Object.entries(summary?.tool_usage || {});

  return (
    <section className="chat-shell dashboard-shell">
      <header className="app-header metrics-header">
        <div>
          <WorkspaceViewTabs currentView="metrics" currentConversationId={currentConversationId} />
          <p className="eyebrow">Observability</p>
          <h1>Metrics</h1>
          <p className="header-subtitle">
            Runtime counters, request latency, trace export state, and recent run outcomes.
          </p>
        </div>

        <div className="metrics-header-actions">
          <span
            className={`context-chip run-status ${summary?.langfuse_enabled ? "running" : "failed"}`}
          >
            {summary?.langfuse_enabled ? "Langfuse on" : "Langfuse off"}
          </span>
          <button
            type="button"
            className="secondary-button"
            onClick={() => void loadSummary()}
            disabled={loading || refreshing}
          >
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      <main className="dashboard-grid metrics-grid">
        {loading && !summary ? <p className="panel-note">Loading metrics...</p> : null}
        {!loading && error ? <p className="panel-error">{error}</p> : null}

        {!loading && summary ? (
          <>
            <MetricCard
              label="Total runs"
              value={formatWholeNumber(totals.runs)}
              hint={`${formatWholeNumber(totals.active_runs)} active right now`}
            />
            <MetricCard
              label="Run success rate"
              value={formatDecimal(runtime.success_rate_pct, "%")}
              hint={`${formatWholeNumber(runtime.succeeded_total)} succeeded • ${formatWholeNumber(runtime.failed_total)} failed`}
            />
            <MetricCard
              label="Avg run latency"
              value={formatDecimal(runtime.average_execution_latency_ms, " ms")}
              hint="Counter-derived execution average"
            />
            <MetricCard
              label="Avg completed run"
              value={formatDecimal(runtime.average_completed_run_latency_ms, " ms")}
              hint="DB-derived completed run duration"
            />
            <MetricCard
              label="Tool calls"
              value={formatWholeNumber(orchestration.tool_calls_total)}
              hint={`${formatWholeNumber(orchestration.fallback_total)} fallback responses`}
            />
            <MetricCard
              label="Token usage"
              value={formatWholeNumber(orchestration.token_usage_total)}
              hint="Total tokens tracked by orchestration"
            />
            <MetricCard
              label="Conversations"
              value={formatWholeNumber(totals.conversations)}
              hint={`${formatWholeNumber(totals.messages)} stored messages`}
            />
            <MetricCard
              label="Documents"
              value={formatWholeNumber(totals.documents)}
              hint={`${formatWholeNumber(api.documents_upload_requests_total)} upload requests`}
            />

            <section className="dashboard-card">
              <p className="dashboard-label">Trace Export</p>
              <h3>{summary.langfuse_enabled ? "Enabled" : "Disabled"}</h3>
              <p className="dashboard-hint">{summary.langfuse_base_url}</p>
            </section>

            <section className="dashboard-card">
              <p className="dashboard-label">API Load</p>
              <h3>{formatWholeNumber(api.chat_submit_requests_total)}</h3>
              <p className="dashboard-hint">
                chat submissions • {formatDecimal(api.average_chat_submit_latency_ms, " ms")} avg
              </p>
            </section>

            <section className="dashboard-card dashboard-card-wide">
              <p className="dashboard-label">Run status mix</p>
              <KeyValueList
                items={runStatusCounts.map(([status, count]) => [
                  formatRunStatusLabel(status) || status,
                  formatWholeNumber(count),
                ])}
                emptyLabel="No runs have been recorded yet."
              />
            </section>

            <section className="dashboard-card dashboard-card-wide">
              <p className="dashboard-label">Tool usage</p>
              <KeyValueList
                items={toolUsage.map(([tool, count]) => [tool, formatWholeNumber(count)])}
                emptyLabel="No tool calls have been recorded yet."
              />
            </section>

            <section className="dashboard-card dashboard-card-wide">
              <p className="dashboard-label">Recent runs</p>
              {summary.recent_runs.length ? (
                <div className="metrics-runs">
                  {summary.recent_runs.map((run) => (
                    <article key={run.id} className="metrics-run-row">
                      <div>
                        <strong>{formatRunStatusLabel(run.status) || run.status}</strong>
                        <p>
                          Run {run.id.slice(0, 8)} • {run.attempt_count} attempt
                          {run.attempt_count === 1 ? "" : "s"}
                        </p>
                      </div>
                      <div className="metrics-run-meta">
                        <span className={`status-pill ${run.status}`}>{formatRunStatusLabel(run.status) || run.status}</span>
                        <span>{formatRelativeTime(run.updated_at)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="dashboard-empty">No runs recorded yet.</p>
              )}
            </section>

            <section className="dashboard-card dashboard-card-wide">
              <p className="dashboard-label">Snapshot</p>
              <p className="dashboard-hint">
                Generated {formatRelativeTime(summary.generated_at)}
                {summary.latest_counter_update
                  ? ` • counters updated ${formatRelativeTime(summary.latest_counter_update)}`
                  : ""}
              </p>
              <p className="dashboard-hint">
                {formatDecimal(orchestration.average_request_latency_ms, " ms")} average orchestration
                latency • {formatDecimal(orchestration.average_langgraph_latency_ms, " ms")} average
                LangGraph invoke latency
              </p>
            </section>
          </>
        ) : null}
      </main>
    </section>
  );
}
