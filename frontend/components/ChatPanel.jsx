import { useEffect } from "react";
import { formatRelativeTime } from "@/lib/formatters";
import WorkspaceViewTabs from "@/components/WorkspaceViewTabs";

function AgentActions({ actions }) {
  if (!actions || actions.length === 0) {
    return null;
  }

  return (
    <details className="agent-actions">
      <summary className="agent-actions-summary">
        Tool activity
        <span className="agent-actions-count">
          {actions.length} step{actions.length === 1 ? "" : "s"}
        </span>
      </summary>

      <div className="agent-actions-body">
        {actions.map((action, idx) => (
          <article key={`${action.tool}-${idx}`} className="agent-action">
            <p className="action-tool">🔧 {action.tool}</p>
            <p>
              <span className="action-label">Input:</span> <code>{String(action.input ?? "")}</code>
            </p>
            <p>
              <span className="action-label">Output:</span> <code>{String(action.output ?? "")}</code>
            </p>
          </article>
        ))}
      </div>
    </details>
  );
}

function ChatBubble({ message }) {
  if (message.isThinking) {
    return (
      <article className="chat-bubble assistant thinking" aria-live="polite">
        <div className="bubble-content">🤔 Thinking...</div>
      </article>
    );
  }

  const isUser = message.role === "user";

  return (
    <article className={`chat-bubble ${isUser ? "user" : "assistant"}`}>
      <div className="bubble-content">{message.content || ""}</div>
      <AgentActions actions={message.agent_actions} />
      <p className="bubble-meta">
        {isUser ? "You" : "Agent"}
        {message.timestamp ? ` • ${formatRelativeTime(message.timestamp)}` : ""}
      </p>
    </article>
  );
}

export default function ChatPanel({
  currentView,
  currentConversationId,
  messages,
  currentConversationTitle,
  isLoadingMessages,
  chatError,
  messageInput,
  isSending,
  onChangeMessage,
  onSendMessage,
  onFocusComposer,
  messageInputRef,
}) {
  useEffect(() => {
    const input = messageInputRef?.current;
    if (!input) {
      return;
    }

    input.style.height = "0px";
    input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
  }, [messageInput, messageInputRef]);

  return (
    <section className="chat-shell">
      <header className="app-header">
        <div>
          <WorkspaceViewTabs currentView={currentView} currentConversationId={currentConversationId} />
          <p className="eyebrow">Personal Agent</p>
          <h1>Assistant Workspace</h1>
          <p className="header-subtitle">
            {currentConversationTitle || "Start typing to open a fresh conversation."}
          </p>
        </div>
      </header>

      <main className="chat-stream" id="chat-container">
        {isLoadingMessages && <p className="panel-note">Loading messages...</p>}

        {!isLoadingMessages && messages.length === 0 && (
          <section className="empty-state" aria-live="polite">
            <h3>Welcome to your Personal Agent</h3>
            <p>Start typing below. Your first message will create a conversation automatically.</p>
            <div className="hint-card">
              <strong>Tip:</strong> The composer stays ready when the page opens, when you return to the tab, and after the agent replies.
            </div>
            <button type="button" className="secondary-button empty-state-button" onClick={onFocusComposer}>
              Focus composer
            </button>
          </section>
        )}

        {!isLoadingMessages && messages.map((message) => <ChatBubble key={message.id} message={message} />)}

        {chatError && <p className="panel-error inline-error">{chatError}</p>}
      </main>

      <footer className="chat-input-row">
        <textarea
          ref={messageInputRef}
          value={messageInput}
          className="chat-input"
          rows={1}
          placeholder="Message your agent..."
          onChange={(event) => onChangeMessage(event.target.value)}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing || event.keyCode === 229) {
              return;
            }

            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSendMessage();
            }
          }}
          disabled={isSending}
        />

        <button
          type="button"
          className="primary-button send-button"
          onClick={onSendMessage}
          disabled={isSending}
        >
          {isSending ? "Sending..." : "Send"}
        </button>
      </footer>
    </section>
  );
}
