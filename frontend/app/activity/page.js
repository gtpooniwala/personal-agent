import WorkspaceApp from "@/components/WorkspaceApp";

export const metadata = {
  title: "Personal Agent Activity",
};

export default function ActivityPage() {
  return <WorkspaceApp view="activity" currentPath="/activity" />;
}
