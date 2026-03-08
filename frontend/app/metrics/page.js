import WorkspaceApp from "@/components/WorkspaceApp";

export const metadata = {
  title: "Personal Agent Metrics",
};

export default function MetricsPage() {
  return <WorkspaceApp view="metrics" currentPath="/metrics" />;
}
