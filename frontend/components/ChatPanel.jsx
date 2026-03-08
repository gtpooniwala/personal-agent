import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { formatRelativeTime } from "@/lib/formatters";
import WorkspaceViewTabs from "@/components/WorkspaceViewTabs";

const DOCUMENT_PROMPT_STARTERS = [
  {
    label: "Summarize selected docs",
    buildPrompt: () => "Summarize the selected documents and highlight the main decisions, dates, and risks.",
  },
  {
    label: "Key facts",
    buildPrompt: () => "What are the most important facts, dates, and action items in the selected documents?",
  },
  {
    label: "Find specific terms",
    buildPrompt: () => "Search the selected documents for pricing, deadlines, renewal, termination, or obligation details.",
  },
];

export function extractDocumentSources(actions) {
  const searchAction = (actions || []).find((action) => action?.tool === "search_documents");
  const output = String(searchAction?.output || "");
  const sources = [];
  const sourcePattern =
    /\*\*\d+\.\s+From '([^']+)' \(section (\d+)\) - ([^:*]+):\*\*\s*([\s\S]*?)(?=\n\*\*\d+\.\s+From '|\n\*Found |\n---\n\*\*Here is a list|$)/g;

  for (const match of output.matchAll(sourcePattern)) {
    const [, filename, section, relevance, excerpt] = match;
    sources.push({
      filename,
      section,
      relevance: relevance.trim(),
      excerpt: excerpt.trim(),
    });
  }

  return sources;
}

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

function SourceCards({ actions }) {
  const sources = extractDocumentSources(actions);
  if (sources.length === 0) {
    return null;
  }

  return (
    <section className="source-card-list" aria-label="Document sources">
      {sources.map((source, index) => (
        <article key={`${source.filename}-${source.section}-${index}`} className="source-card">
          <div className="source-card-header">
            <strong>{source.filename}</strong>
            <span className="source-card-meta">
              Section {source.section} • {source.relevance}
            </span>
          </div>
          <p>{source.excerpt}</p>
        </article>
      ))}
    </section>
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
      {!isUser ? <SourceCards actions={message.agent_actions} /> : null}
      <AgentActions actions={message.agent_actions} />
      <p className="bubble-meta">
        {isUser ? "You" : "Agent"}
        {message.timestamp ? ` • ${formatRelativeTime(message.timestamp)}` : ""}
      </p>
    </article>
  );
}

const ChatPanel = forwardRef(function ChatPanel({
  currentView,
  currentConversationId,
  messages,
  currentConversationTitle,
  activeRun,
  isLoadingMessages,
  chatError,
  messageInput,
  isSending,
  selectedDocumentDetails = [],
  onChangeMessage,
  onChoosePromptStarter,
  onSendMessage,
  onFocusComposer,
}, messageInputRef) {
  const localMessageInputRef = useRef(null);

  useImperativeHandle(messageInputRef, () => localMessageInputRef.current, []);

  useEffect(() => {
    const input = localMessageInputRef.current;
    if (!input) {
      return;
    }

    input.style.height = "0px";
    input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
  }, [messageInput]);

  const hasSelectedDocuments = selectedDocumentDetails.length > 0;

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

      {(activeRun?.status || hasSelectedDocuments) && (
        <section className="active-context-bar">
          {activeRun?.status ? (
            <span className={`context-chip run-status ${activeRun.status}`}>
              Run {activeRun.status}
            </span>
          ) : null}

          {hasSelectedDocuments ? (
            <div className="selected-documents-strip" aria-label="Selected documents">
              {selectedDocumentDetails.map((document) => (
                <span key={document.id} className="context-chip selected-document-chip">
                  {document.filename}
                </span>
              ))}
            </div>
          ) : null}
        </section>
      )}

      {hasSelectedDocuments ? (
        <section className="prompt-starter-bar" aria-label="Document prompt starters">
          <p className="prompt-starter-label">Ask about your selected documents</p>
          <div className="prompt-starter-list">
            {DOCUMENT_PROMPT_STARTERS.map((starter) => (
              <button
                key={starter.label}
                type="button"
                className="secondary-button prompt-starter-button"
                onClick={() => onChoosePromptStarter?.(starter.buildPrompt(selectedDocumentDetails))}
              >
                {starter.label}
              </button>
            ))}
          </div>
        </section>
      ) : null}

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
          ref={localMessageInputRef}
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
});

export default ChatPanel;
