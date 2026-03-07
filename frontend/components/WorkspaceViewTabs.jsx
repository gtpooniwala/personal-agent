import Link from "next/link";

function buildHref(path, conversationId) {
  if (!conversationId) {
    return path;
  }

  return `${path}?conversation=${encodeURIComponent(conversationId)}`;
}

export default function WorkspaceViewTabs({ currentView, currentConversationId }) {
  return (
    <nav className="workspace-tabs" aria-label="Workspace views">
      <Link
        href={buildHref("/", currentConversationId)}
        className={`workspace-tab ${currentView === "chat" ? "active" : ""}`}
      >
        Chat
      </Link>
      <Link
        href={buildHref("/activity", currentConversationId)}
        className={`workspace-tab ${currentView === "activity" ? "active" : ""}`}
      >
        Activity
      </Link>
      <Link
        href={buildHref("/metrics", currentConversationId)}
        className={`workspace-tab ${currentView === "metrics" ? "active" : ""}`}
      >
        Metrics
      </Link>
    </nav>
  );
}
