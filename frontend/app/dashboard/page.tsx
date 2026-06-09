import { cookies } from "next/headers";
import { buildApiUrl } from "@/lib/api";

interface UserOut {
  user_id: string;
  name: string;
  email: string;
  role: string;
}

async function getMe(): Promise<UserOut | null> {
  const cookieStore = await cookies();
  const session = cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) return null;

  try {
    const res = await fetch(buildApiUrl("/api/v1/auth/me"), {
      headers: { Cookie: `${session.name}=${session.value}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const user = await getMe();

  return (
    <main className="min-h-screen bg-muted/20 p-8">
      <div className="max-w-4xl mx-auto">
        <header className="mb-8">
          <h1 className="text-2xl font-semibold">
            Olá, {user?.name ?? "colaborador"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Bem-vindo ao IT Helpdesk
          </p>
        </header>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <a
            href="/chat/new"
            className="rounded-xl border bg-card p-6 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
          >
            <div className="text-4xl mb-3">💬</div>
            <h2 className="font-semibold text-lg">Abrir chamado</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Descreva seu problema e a IA vai te ajudar
            </p>
          </a>

          <div className="rounded-xl border bg-card p-6 shadow-sm">
            <div className="text-4xl mb-3">📋</div>
            <h2 className="font-semibold text-lg">Meus chamados</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Acompanhe o status dos seus tickets
            </p>
          </div>

          <div className="rounded-xl border bg-card p-6 shadow-sm">
            <div className="text-4xl mb-3">📚</div>
            <h2 className="font-semibold text-lg">Base de conhecimento</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Artigos e resoluções documentadas
            </p>
          </div>
        </div>

        {user && (
          <p className="mt-8 text-xs text-muted-foreground">
            Papel: <code className="font-mono">{user.role}</code> · ID: {user.user_id}
          </p>
        )}
      </div>
    </main>
  );
}
