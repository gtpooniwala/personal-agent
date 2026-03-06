import { formatRelativeTime, truncateText } from "@/lib/formatters";

export default function ConversationList({
  conversations,
  currentConversationId,
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

                return (
                  <button
                    key={conversation.id}
                    type="button"
                    className={`conversation-card ${isActive ? "active" : ""}`}
                    onClick={() => onSelectConversation(conversation.id)}
                  >
                    <span className="conversation-title">{truncateText(conversation.title, 45)}</span>
                    <span className="conversation-date">
                      {formatRelativeTime(conversation.updated_at)}
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
