import WorkspaceApp from "@/components/WorkspaceApp";

export default function HomePage({ searchParams }) {
  return (
    <WorkspaceApp
      view="chat"
      currentPath="/"
      initialConversationId={searchParams?.conversation || null}
    />
  );
}
