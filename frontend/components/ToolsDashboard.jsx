import { useState, useEffect, useCallback } from "react";
import { apiCall } from "@/lib/api";

export default function ToolsDashboard() {
  const [allTools, setAllTools] = useState([]);
  const [gmailStatus, setGmailStatus] = useState(null);
  const [toolsLoading, setToolsLoading] = useState(true);
  const [toolsError, setToolsError] = useState(null);
  const [gmailLoading, setGmailLoading] = useState(true);
  const [gmailError, setGmailError] = useState(null);

  const fetchTools = useCallback(async () => {
    setToolsError(null);
    try {
      const tools = await apiCall("/tools/info");
      setAllTools(tools.sort((a, b) => a.name.localeCompare(b.name)));
    } catch (err) {
      console.error("Failed to load tools list:", err);
      setToolsError(err?.message ?? "Failed to load tools");
    } finally {
      setToolsLoading(false);
    }
  }, []);

  const fetchGmailStatus = useCallback(async () => {
    setGmailLoading(true);
    setGmailError(null);
    try {
      const status = await apiCall("/gmail/status");
      setGmailStatus(status);
    } catch (err) {
      setGmailStatus(null);
      setGmailError(err?.message ?? "Failed to load Gmail status");
    } finally {
      setGmailLoading(false);
    }
  }, []);

  useEffect(() => {
    // Detect ?gmail=connected after OAuth redirect
    const params = new URLSearchParams(window.location.search);
    if (params.get("gmail") === "connected") {
      params.delete("gmail");
      const newSearch = params.toString();
      const newUrl =
        window.location.pathname + (newSearch ? `?${newSearch}` : "") + window.location.hash;
      window.history.replaceState(null, "", newUrl);
    }

    fetchTools();
    fetchGmailStatus();
  }, [fetchTools, fetchGmailStatus]);

  function handleGmailConnect() {
    // return_to must be an origin registered in the backend's ALLOWED_ORIGINS env var.
    // Add any new deployment URLs there before enabling Gmail connect on that host.
    const returnTo = new URL(window.location.href).toString();
    // Full browser navigation required — OAuth flow must follow redirects, not fetch.
    window.location.href = `/api/agent/gmail/connect?return_to=${encodeURIComponent(returnTo)}`;
  }

  async function handleGmailDisconnect() {
    setGmailLoading(true);
    setGmailError(null);
    try {
      const status = await apiCall("/gmail/connection", { method: "DELETE" });
      setGmailStatus(status);
      await fetchTools();
    } catch (err) {
      setGmailError(err?.message ?? "Failed to disconnect Gmail");
    } finally {
      setGmailLoading(false);
    }
  }

  return (
    <div className="tools-panel-body">
      {/* All tools list */}
      <section>
        {toolsLoading && <p className="panel-note">Loading tools...</p>}
        {!toolsLoading && toolsError && <p className="panel-error">{toolsError}</p>}
        {!toolsLoading && !toolsError &&
          allTools.map((tool) => (
            // tool.name is unique — the registry uses a dict keyed by name
            <div key={tool.name} className="tool-row">
              <span className="tool-name" title={tool.description}>
                {tool.name}
              </span>
              <span className={`tool-badge ${tool.active ? "active" : "inactive"}`}>
                {tool.active ? "Active" : "Inactive"}
              </span>
            </div>
          ))}
      </section>

      {/* Gmail integration card */}
      <div className="gmail-card">
        <div className="gmail-card-header">
          <span className="gmail-card-label">Gmail</span>
          {gmailStatus?.connected && gmailStatus?.account_label && (
            <span className="gmail-card-account">{gmailStatus.account_label}</span>
          )}
        </div>

        {gmailLoading && <p className="panel-note">Loading...</p>}
        {!gmailLoading && gmailError && <p className="panel-error">{gmailError}</p>}

        {!gmailLoading && !gmailError && gmailStatus && (
          <div className="gmail-card-actions">
            {gmailStatus.connected ? (
              <button
                type="button"
                className="secondary-button gmail-disconnect-button"
                onClick={handleGmailDisconnect}
              >
                Disconnect
              </button>
            ) : (
              <button
                type="button"
                className="primary-button gmail-connect-button"
                onClick={handleGmailConnect}
                disabled={!gmailStatus.ready}
                title={
                  !gmailStatus.ready ? gmailStatus?.reasons?.join("; ") ?? "Gmail not configured" : undefined
                }
              >
                Connect Gmail
              </button>
            )}
            <button
              type="button"
              className="secondary-button"
              onClick={fetchGmailStatus}
              aria-label="Refresh Gmail status"
            >
              Refresh
            </button>
          </div>
        )}

        {!gmailLoading && gmailStatus?.reasons?.some(Boolean) && (
          <p className="panel-note" style={{ fontSize: "11px", marginTop: 0 }}>
            {gmailStatus.reasons.join(" · ")}
          </p>
        )}
      </div>
    </div>
  );
}
