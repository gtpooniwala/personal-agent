import { formatRelativeTime, truncateText } from "@/lib/formatters";

function formatRunStatusLabel(status) {
  switch (status) {
    case "queued":
      return "Queued";
    case "running":
      return "Running";
    case "retrying":
      return "Retrying";
    case "failed":
      return "Failed";
    default:
      return "";
  }
}

export default function ConversationList({
  conversations,
  currentConversationId,
  runStateByConversation,
  isLoading,
  error,
  isCollapsed,
  onToggleCollapse,
  onCreateConversation,
  onSelectConversation,
}) {
  return (
    <aside className={`panel panel-left ${isCollapsed ? "collapsed" : ""}`}>
      <button
        className="collapse-button"
        type="button"
        onClick={onToggleCollapse}
        aria-label={isCollapsed ? "Expand conversations" : "Collapse conversations"}
      >
        {isCollapsed ? "⮞" : "⮜"}
      </button>

      {!isCollapsed && (
        <>
          <div className="panel-header">
            <p className="eyebrow">Session</p>
            <h2>Conversations</h2>
          </div>

          <button className="primary-button" type="button" onClick={onCreateConversation}>
            + New Chat
          </button>

          <div className="panel-body scrollable">
            {isLoading && <p className="panel-note">Loading conversations...</p>}
            {!isLoading && error && <p className="panel-error">{error}</p>}
            {!isLoading && !error && conversations.length === 0 && (
              <p className="panel-note">No conversations yet.</p>
            )}

            {!isLoading &&
              !error &&
              conversations.map((conversation) => {
                const isActive = conversation.id === currentConversationId;
                const runState = runStateByConversation?.[conversation.id];
                const runLabel = formatRunStatusLabel(runState?.status);

                return (
                  <button
                    key={conversation.id}
                    type="button"
                    className={`conversation-card ${isActive ? "active" : ""}`}
                    onClick={() => onSelectConversation(conversation.id)}
                  >
                    <span className="conversation-title">{truncateText(conversation.title, 45)}</span>
                    <span className="conversation-meta-row">
                      <span className="conversation-date">
                        {formatRelativeTime(conversation.updated_at)}
                      </span>
                      {runLabel && (
                        <span className={`conversation-status ${runState.status}`}>{runLabel}</span>
                      )}
                    </span>
                  </button>
                );
              })}
          </div>
        </>
      )}
    </aside>
  );
}
