"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface UserAdmin {
  uuid: string;
  name: string;
  email: string;
  override_role: string | null;
}

const ROLE_LABEL: Record<string, string> = {
  it_admin: "Admin TI",
  it_lead: "Líder TI",
};

const ROLE_COLOR: Record<string, string> = {
  it_admin: "bg-red-500/15 text-red-400",
  it_lead: "bg-blue-500/15 text-blue-400",
};

async function getCsrfHeaders(): Promise<HeadersInit> {
  await fetch("/api/v1/auth/csrf");
  const csrf = document.cookie.split("; ").find((c) => c.startsWith("csrf_token="))?.split("=")[1] ?? "";
  return { "Content-Type": "application/json", "X-CSRF-Token": csrf };
}

export default function AdminUsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<UserAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  async function load() {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/admin/users");
      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) { setError("Erro ao carregar usuários"); return; }
      setUsers(await res.json() as UserAdmin[]);
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, []);

  async function handleGrant(uuid: string, role: string) {
    setSaving(uuid + ":" + role);
    try {
      const headers = await getCsrfHeaders();
      const res = await fetch(`/api/v1/admin/roles/${uuid}`, {
        method: "POST",
        headers,
        body: JSON.stringify({ role }),
      });
      if (!res.ok) {
        const err = await res.json() as { detail?: string };
        setError(err.detail ?? "Erro ao conceder papel");
        return;
      }
      await load();
    } finally { setSaving(null); }
  }

  async function handleRevoke(uuid: string) {
    setSaving(uuid + ":revoke");
    try {
      const headers = await getCsrfHeaders();
      const res = await fetch(`/api/v1/admin/roles/${uuid}`, { method: "DELETE", headers });
      if (!res.ok) {
        const err = await res.json() as { detail?: string };
        setError(err.detail ?? "Erro ao revogar papel");
        return;
      }
      await load();
    } finally { setSaving(null); }
  }

  const filtered = users.filter((u) =>
    !search ||
    u.name.toLowerCase().includes(search.toLowerCase()) ||
    u.email.toLowerCase().includes(search.toLowerCase())
  );
  const withOverrides = filtered.filter((u) => u.override_role);
  const withoutOverrides = filtered.filter((u) => !u.override_role);

  if (loading) return <div className="p-6 text-zinc-500 text-sm">Carregando...</div>;

  return (
    <div className="p-5 max-w-4xl">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-zinc-100">Usuários & Papéis</h2>
        <p className="text-xs text-zinc-500 mt-0.5">
          {users.filter((u) => u.override_role).length} usuários com papel explícito de {users.length} total
        </p>
      </div>

      {error && <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>}

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Buscar por nome ou e-mail..."
        className="w-full mb-4 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
      />

      {withOverrides.length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">Com Papel Explícito</h3>
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500">
                  <th className="text-left px-4 py-3 font-medium">Nome</th>
                  <th className="text-left px-4 py-3 font-medium">E-mail</th>
                  <th className="text-left px-4 py-3 font-medium">Papel</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {withOverrides.map((u) => (
                  <tr key={u.uuid} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="px-4 py-3 font-medium text-zinc-200">{u.name}</td>
                    <td className="px-4 py-3 text-zinc-400">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-[11px] ${ROLE_COLOR[u.override_role!] ?? ""}`}>
                        {ROLE_LABEL[u.override_role!] ?? u.override_role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2 justify-end">
                        {u.override_role !== "it_admin" && (
                          <button
                            onClick={() => void handleGrant(u.uuid, "it_admin")}
                            disabled={!!saving}
                            className="text-red-400 hover:text-red-300 transition-colors disabled:opacity-50 text-[11px]"
                          >
                            → Admin
                          </button>
                        )}
                        {u.override_role !== "it_lead" && (
                          <button
                            onClick={() => void handleGrant(u.uuid, "it_lead")}
                            disabled={!!saving}
                            className="text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50 text-[11px]"
                          >
                            → Líder
                          </button>
                        )}
                        <button
                          onClick={() => void handleRevoke(u.uuid)}
                          disabled={saving === u.uuid + ":revoke"}
                          className="text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-50 text-[11px]"
                        >
                          {saving === u.uuid + ":revoke" ? "..." : "Revogar"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div>
        <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">
          {withOverrides.length > 0 ? "Demais Usuários" : "Todos os Usuários"}
        </h3>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500">
                <th className="text-left px-4 py-3 font-medium">Nome</th>
                <th className="text-left px-4 py-3 font-medium">E-mail</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {withoutOverrides.map((u) => (
                <tr key={u.uuid} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="px-4 py-3 font-medium text-zinc-200">{u.name}</td>
                  <td className="px-4 py-3 text-zinc-400">{u.email}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => void handleGrant(u.uuid, "it_lead")}
                        disabled={!!saving}
                        className="text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50 text-[11px]"
                      >
                        Líder TI
                      </button>
                      <button
                        onClick={() => void handleGrant(u.uuid, "it_admin")}
                        disabled={!!saving}
                        className="text-red-400 hover:text-red-300 transition-colors disabled:opacity-50 text-[11px]"
                      >
                        Admin TI
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {withoutOverrides.length === 0 && (
                <tr><td colSpan={3} className="px-4 py-6 text-center text-zinc-600">Nenhum usuário encontrado</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
