import { formatRelativeTime } from "@/lib/formatters";

function AgentActions({ actions }) {
  if (!actions || actions.length === 0) {
    return null;
  }

  return (
    <div className="agent-actions">
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
  tools,
  messages,
  isLoadingMessages,
  chatError,
  messageInput,
  isSending,
  onChangeMessage,
  onSendMessage,
}) {
  const toolsText =
    tools.length > 0 ? `Available tools: ${tools.map((tool) => tool.name).join(", ")}` : "Loading tools...";

  return (
    <section className="chat-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Personal Agent</p>
          <h1>Assistant Workspace</h1>
        </div>
        <p className="tools-info">{toolsText}</p>
      </header>

      <main className="chat-stream" id="chat-container">
        {isLoadingMessages && <p className="panel-note">Loading messages...</p>}

        {!isLoadingMessages && messages.length === 0 && (
          <section className="empty-state" aria-live="polite">
            <h3>Welcome to your Personal Agent</h3>
            <p>Start a conversation below. Ask questions, run tools, or query your uploaded PDFs.</p>
            <div className="hint-card">
              <strong>Tip:</strong> Upload PDF documents in the right panel and select them for RAG answers.
            </div>
          </section>
        )}

        {!isLoadingMessages && messages.map((message) => <ChatBubble key={message.id} message={message} />)}

        {chatError && <p className="panel-error inline-error">{chatError}</p>}
      </main>

      <footer className="chat-input-row">
        <input
          type="text"
          value={messageInput}
          className="chat-input"
          placeholder="Type your message here..."
          onChange={(event) => onChangeMessage(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
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
