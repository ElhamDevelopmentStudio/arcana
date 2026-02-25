import Card from "@/shared/ui/Card";
import StatusChip from "@/shared/ui/StatusChip";

function AuthPlaceholderPage() {
  return (
    <main className="app-root">
      <div className="shell-grid">
        <Card
          title="Authentication"
          subtitle="Auth routes are scaffolded and will become active once backend auth requirements are implemented."
          action={<StatusChip tone="accent">Pending</StatusChip>}
        >
          <p>Route shell is ready: `/auth`.</p>
        </Card>
      </div>
    </main>
  );
}

export default AuthPlaceholderPage;
