import WorkspaceApp from "@/components/WorkspaceApp";

export const metadata = {
  title: "Personal Agent Metrics",
};

export default function MetricsPage({ searchParams }) {
  return (
    <WorkspaceApp
      view="metrics"
      currentPath="/metrics"
      initialConversationId={searchParams?.conversation || null}
    />
  );
}
