import { formatRelativeTime, truncateText } from "@/lib/formatters";
import WorkspaceViewTabs from "@/components/WorkspaceViewTabs";

function formatRunLabel(status) {
  switch (status) {
    case "queued":
      return "Queued";
    case "running":
      return "Running";
    case "retrying":
      return "Retrying";
    case "succeeded":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelling":
      return "Cancelling";
    case "cancelled":
      return "Cancelled";
    default:
      return "Idle";
  }
}

function describeRunEvent(event) {
  if (!event) {
    return "No recent activity";
  }

  if (event.type === "tool_result" && event.tool) {
    return `Used ${event.tool}`;
  }

  return event.message || formatRunLabel(event.status);
}

function StatCard({ label, value, hint }) {
  return (
    <article className="dashboard-card">
      <p className="dashboard-label">{label}</p>
      <h3>{value}</h3>
      <p className="dashboard-hint">{hint}</p>
    </article>
  );
}

export default function ActivityDashboard({
  currentConversationId,
  currentConversationTitle,
  activeRun,
  selectedDocumentCount,
  tools,
  conversations,
}) {
  const latestEvent = activeRun?.latestEvent || null;
  const recentConversations = conversations.slice(0, 6);

  return (
    <section className="chat-shell dashboard-shell">
      <header className="app-header">
        <div>
          <WorkspaceViewTabs currentView="activity" currentConversationId={currentConversationId} />
          <p className="eyebrow">Workspace</p>
          <h1>Activity</h1>
          <p className="header-subtitle">
            Minimal run and context details live here so chat stays clean.
          </p>
        </div>
      </header>

      <main className="dashboard-grid">
        <StatCard
          label="Conversation"
          value={currentConversationTitle || "No conversation selected"}
          hint={currentConversationTitle ? "Current focus in the sidebar." : "Pick a conversation from the left rail."}
        />
        <StatCard
          label="Run status"
          value={formatRunLabel(activeRun?.status)}
          hint={latestEvent ? describeRunEvent(latestEvent) : "No recent run for this conversation."}
        />
        <StatCard
          label="Documents"
          value={`${selectedDocumentCount}`}
          hint={
            selectedDocumentCount > 0
              ? "Selected for document search."
              : "No documents selected for this conversation."
          }
        />
        <StatCard
          label="Tools"
          value={`${tools.length}`}
          hint={tools.length > 0 ? tools.map((tool) => tool.name).join(", ") : "Loading tools"}
        />

        <section className="dashboard-card dashboard-card-wide">
          <p className="dashboard-label">Recent run events</p>
          {activeRun?.events?.length ? (
            <ol className="dashboard-timeline">
              {activeRun.events.map((event) => (
                <li key={event.event_id}>
                  <span className={`timeline-dot ${event.status || "idle"}`} />
                  <div>
                    <strong>{describeRunEvent(event)}</strong>
                    <p>{formatRelativeTime(event.created_at)}</p>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="dashboard-empty">No run events yet for this conversation.</p>
          )}
        </section>

        <section className="dashboard-card dashboard-card-wide">
          <p className="dashboard-label">Recent conversations</p>
          {recentConversations.length > 0 ? (
            <div className="dashboard-list">
              {recentConversations.map((conversation) => (
                <div
                  key={conversation.id}
                  className={`dashboard-list-row ${conversation.id === currentConversationId ? "active" : ""}`}
                >
                  <span>{truncateText(conversation.title, 44)}</span>
                  <span>{formatRelativeTime(conversation.updated_at)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="dashboard-empty">No conversations yet.</p>
          )}
        </section>
      </main>
    </section>
  );
}
