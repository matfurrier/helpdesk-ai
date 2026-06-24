"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface Application {
  id: number;
  app_name: string;
  description: string | null;
  created_at: string;
  user_uuids: string[];
}

interface UserOption {
  uuid: string;
  name: string;
  email: string;
}

function AppDialog({
  open,
  onClose,
  onSave,
  app,
  users,
}: {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
  app: Application | null;
  users: UserOption[];
}) {
  const [appName, setAppName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedUuids, setSelectedUuids] = useState<string[]>([]);
  const [userSearch, setUserSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setAppName(app?.app_name ?? "");
    setDescription(app?.description ?? "");
    setSelectedUuids(app?.user_uuids ?? []);
    setUserSearch("");
    setError("");
  }, [app, open]);

  function toggleUser(uuid: string) {
    setSelectedUuids((prev) =>
      prev.includes(uuid) ? prev.filter((u) => u !== uuid) : [...prev, uuid]
    );
  }

  async function handleSubmit() {
    if (!appName.trim()) { setError("Nome é obrigatório"); return; }
    setSaving(true);
    setError("");
    try {
      const headers = { "Content-Type": "application/json" };
      const payload = {
        app_name: appName.trim(),
        description: description.trim() || null,
        user_uuids: selectedUuids,
      };
      const url = app ? `/api/v1/admin/applications/${app.id}` : "/api/v1/admin/applications";
      const method = app ? "PATCH" : "POST";
      const res = await fetch(url, { method, headers, body: JSON.stringify(payload) });
      if (!res.ok) {
        const err = await res.json() as { detail?: string };
        setError(err.detail ?? "Erro ao salvar");
        return;
      }
      onSave();
    } finally { setSaving(false); }
  }

  if (!open) return null;

  const filteredUsers = users.filter(
    (u) =>
      u.name.toLowerCase().includes(userSearch.toLowerCase()) ||
      u.email.toLowerCase().includes(userSearch.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 w-full max-w-md shadow-2xl flex flex-col gap-4 max-h-[90vh] overflow-y-auto">
        <h3 className="text-sm font-semibold text-zinc-100">
          {app ? "Editar Aplicação" : "Nova Aplicação"}
        </h3>

        {error && (
          <div className="px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Nome</label>
            <input
              autoFocus
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              placeholder="Nome da aplicação"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Descrição (opcional)</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Descrição breve"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs text-zinc-500 mb-2">
            Usuários com acesso{" "}
            <span className="text-zinc-600">({selectedUuids.length} selecionados)</span>
          </label>
          <input
            value={userSearch}
            onChange={(e) => setUserSearch(e.target.value)}
            placeholder="Buscar usuário..."
            className="w-full mb-2 bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-600"
          />
          <div className="max-h-48 overflow-y-auto bg-zinc-800 border border-zinc-700 rounded divide-y divide-zinc-700">
            {filteredUsers.length === 0 && (
              <div className="px-3 py-4 text-xs text-zinc-600 text-center">Nenhum usuário encontrado</div>
            )}
            {filteredUsers.map((u) => (
              <label
                key={u.uuid}
                className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-zinc-700/40 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedUuids.includes(u.uuid)}
                  onChange={() => toggleUser(u.uuid)}
                  className="accent-blue-500"
                />
                <div>
                  <div className="text-xs text-zinc-200">{u.name}</div>
                  <div className="text-[11px] text-zinc-500">{u.email}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="flex gap-2 justify-end pt-1">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={() => void handleSubmit()}
            disabled={saving || !appName.trim()}
            className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {saving ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AdminApplicationsPage() {
  const router = useRouter();
  const [applications, setApplications] = useState<Application[]>([]);
  const [filtered, setFiltered] = useState<Application[]>([]);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [selected, setSelected] = useState<Application | null>(null);

  const [confirmDelete, setConfirmDelete] = useState<Application | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [appsRes, usersRes] = await Promise.all([
        fetch("/api/v1/admin/applications"),
        fetch("/api/v1/admin/users"),
      ]);
      if (appsRes.status === 401 || usersRes.status === 401) {
        router.push("/login");
        return;
      }
      if (!appsRes.ok) { setError("Erro ao carregar aplicações"); return; }
      const appsData = await appsRes.json() as Application[];
      setApplications(appsData);
      setFiltered(appsData);
      if (usersRes.ok) {
        const usersData = await usersRes.json() as UserOption[];
        setUsers(usersData);
      }
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, []);

  function handleSearch(q: string) {
    setSearch(q);
    const ql = q.toLowerCase();
    setFiltered(
      applications.filter(
        (a) =>
          a.app_name.toLowerCase().includes(ql) ||
          (a.description ?? "").toLowerCase().includes(ql)
      )
    );
  }

  async function handleDelete(app: Application) {
    setDeleting(true);
    setError("");
    try {
      const headers = { "Content-Type": "application/json" };
      const res = await fetch(`/api/v1/admin/applications/${app.id}`, {
        method: "DELETE",
        headers,
      });
      if (!res.ok) {
        const err = await res.json() as { detail?: string };
        setError(err.detail ?? "Erro ao excluir");
        return;
      }
      setConfirmDelete(null);
      await load();
    } finally { setDeleting(false); }
  }

  function getUserName(uuid: string): string {
    return users.find((u) => u.uuid === uuid)?.name ?? uuid.slice(0, 8) + "…";
  }

  if (loading) return <div className="p-6 text-zinc-500 text-sm">Carregando...</div>;

  return (
    <div className="p-5 max-w-4xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">Aplicações</h2>
          <p className="text-xs text-zinc-500 mt-0.5">{applications.length} aplicações</p>
        </div>
        <button
          onClick={() => { setSelected(null); setDialogOpen(true); }}
          className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors"
        >
          + Nova Aplicação
        </button>
      </div>

      {error && (
        <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>
      )}

      <input
        value={search}
        onChange={(e) => handleSearch(e.target.value)}
        placeholder="Buscar por nome ou descrição..."
        className="w-full mb-3 bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-600"
      />

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500">
              <th className="text-left px-4 py-3 font-medium">Nome</th>
              <th className="text-left px-4 py-3 font-medium hidden sm:table-cell">Descrição</th>
              <th className="text-left px-4 py-3 font-medium">Usuários</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {filtered.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-zinc-600">
                  {search ? "Nenhum resultado." : "Nenhuma aplicação cadastrada."}
                </td>
              </tr>
            )}
            {filtered.map((app) => (
              <tr key={app.id} className="hover:bg-zinc-800/30 transition-colors">
                <td className="px-4 py-3 font-medium text-zinc-200">{app.app_name}</td>
                <td className="px-4 py-3 text-zinc-400 hidden sm:table-cell">
                  {app.description ?? "—"}
                </td>
                <td className="px-4 py-3">
                  {app.user_uuids.length === 0 ? (
                    <span className="text-zinc-600">—</span>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {app.user_uuids.slice(0, 3).map((uuid) => (
                        <span
                          key={uuid}
                          className="px-1.5 py-0.5 bg-zinc-700/50 text-zinc-300 rounded text-[11px]"
                        >
                          {getUserName(uuid)}
                        </span>
                      ))}
                      {app.user_uuids.length > 3 && (
                        <span className="px-1.5 py-0.5 bg-zinc-700/30 text-zinc-500 rounded text-[11px]">
                          +{app.user_uuids.length - 3}
                        </span>
                      )}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-3 justify-end">
                    <button
                      onClick={() => { setSelected(app); setDialogOpen(true); }}
                      className="text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      Editar
                    </button>
                    <button
                      onClick={() => { setConfirmDelete(app); setError(""); }}
                      className="text-red-500 hover:text-red-400 transition-colors"
                    >
                      Excluir
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <AppDialog
        open={dialogOpen}
        onClose={() => { setDialogOpen(false); setSelected(null); }}
        onSave={() => { setDialogOpen(false); setSelected(null); void load(); }}
        app={selected}
        users={users}
      />

      {/* Modal de confirmação de exclusão */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 w-full max-w-sm shadow-2xl">
            <h3 className="text-sm font-semibold text-zinc-100 mb-2">Excluir aplicação</h3>
            <p className="text-xs text-zinc-400 mb-5">
              Tem certeza que deseja excluir{" "}
              <span className="font-medium text-zinc-200">{confirmDelete.app_name}</span>?
              Os vínculos com usuários serão removidos automaticamente.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setConfirmDelete(null)}
                className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => void handleDelete(confirmDelete)}
                disabled={deleting}
                className="px-3 py-1.5 bg-red-600 text-white text-xs rounded-md hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleting ? "Excluindo..." : "Excluir"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
