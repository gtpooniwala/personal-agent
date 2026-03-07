import WorkspaceApp from "@/components/WorkspaceApp";

export const metadata = {
  title: "Personal Agent Activity",
};

export default function ActivityPage({ searchParams }) {
  return (
    <WorkspaceApp
      view="activity"
      currentPath="/activity"
      initialConversationId={searchParams?.conversation || null}
    />
  );
}
