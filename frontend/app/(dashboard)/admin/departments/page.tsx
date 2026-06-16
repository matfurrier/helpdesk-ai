"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface Department {
  id: number;
  uuid: string;
  name: string;
  created_at: string;
}

async function getCsrfHeaders(): Promise<HeadersInit> {
  await fetch("/api/v1/auth/csrf");
  const csrf = document.cookie.split("; ").find((c) => c.startsWith("csrf_token="))?.split("=")[1] ?? "";
  return { "Content-Type": "application/json", "X-CSRF-Token": csrf };
}

export default function AdminDepartmentsPage() {
  const router = useRouter();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [filtered, setFiltered] = useState<Department[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  const [editing, setEditing] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [saving, setSaving] = useState<number | null>(null);

  const [confirmDelete, setConfirmDelete] = useState<Department | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/admin/departments");
      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) { setError("Erro ao carregar departamentos"); return; }
      const data = await res.json() as Department[];
      setDepartments(data);
      setFiltered(data);
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, []);

  function handleSearch(q: string) {
    setSearch(q);
    const ql = q.toLowerCase();
    setFiltered(departments.filter((d) => d.name.toLowerCase().includes(ql)));
  }

  function startEdit(dept: Department) {
    setEditing(dept.id);
    setEditName(dept.name);
  }

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    setError("");
    try {
      const headers = await getCsrfHeaders();
      const res = await fetch("/api/v1/admin/departments", {
        method: "POST",
        headers,
        body: JSON.stringify({ name: newName.trim() }),
      });
      if (!res.ok) {
        const err = await res.json() as { detail?: string };
        setError(err.detail ?? "Erro ao criar departamento");
        return;
      }
      setNewName("");
      setShowForm(false);
      await load();
    } finally { setCreating(false); }
  }

  async function handleSaveEdit(dept: Department) {
    if (!editName.trim()) return;
    setSaving(dept.id);
    setError("");
    try {
      const headers = await getCsrfHeaders();
      const res = await fetch(`/api/v1/admin/departments/${dept.id}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ name: editName.trim() }),
      });
      if (!res.ok) {
        const err = await res.json() as { detail?: string };
        setError(err.detail ?? "Erro ao salvar");
        return;
      }
      setEditing(null);
      await load();
    } finally { setSaving(null); }
  }

  async function handleDelete(dept: Department) {
    setDeleting(true);
    setError("");
    try {
      const headers = await getCsrfHeaders();
      const res = await fetch(`/api/v1/admin/departments/${dept.id}`, {
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

  if (loading) return <div className="p-6 text-zinc-500 text-sm">Carregando...</div>;

  return (
    <div className="p-5 max-w-3xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">Departamentos</h2>
          <p className="text-xs text-zinc-500 mt-0.5">{departments.length} departamentos</p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setNewName(""); setError(""); }}
          className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors"
        >
          + Novo Departamento
        </button>
      </div>

      {error && (
        <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>
      )}

      {showForm && (
        <div className="mb-4 bg-zinc-900 border border-zinc-700 rounded-lg p-4 space-y-3">
          <h3 className="text-xs font-medium text-zinc-400">Novo Departamento</h3>
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void handleCreate(); }}
            placeholder="Nome do departamento"
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setShowForm(false); setNewName(""); }}
              className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={() => void handleCreate()}
              disabled={creating || !newName.trim()}
              className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {creating ? "Criando..." : "Criar"}
            </button>
          </div>
        </div>
      )}

      <input
        value={search}
        onChange={(e) => handleSearch(e.target.value)}
        placeholder="Buscar por nome..."
        className="w-full mb-3 bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-600"
      />

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500">
              <th className="text-left px-4 py-3 font-medium">Nome</th>
              <th className="text-left px-4 py-3 font-medium hidden sm:table-cell">UUID</th>
              <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Criado em</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {filtered.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-zinc-600">
                  {search ? "Nenhum resultado." : "Nenhum departamento cadastrado."}
                </td>
              </tr>
            )}
            {filtered.map((dept) => (
              <tr key={dept.id} className="hover:bg-zinc-800/30 transition-colors">
                {editing === dept.id ? (
                  <>
                    <td className="px-4 py-3" colSpan={3}>
                      <input
                        autoFocus
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") void handleSaveEdit(dept); if (e.key === "Escape") setEditing(null); }}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-200 focus:outline-none focus:border-zinc-500"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-3 justify-end">
                        <button
                          onClick={() => setEditing(null)}
                          className="text-zinc-500 hover:text-zinc-300 transition-colors"
                        >
                          Cancelar
                        </button>
                        <button
                          onClick={() => void handleSaveEdit(dept)}
                          disabled={saving === dept.id || !editName.trim()}
                          className="text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50"
                        >
                          {saving === dept.id ? "..." : "Salvar"}
                        </button>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-3 font-medium text-zinc-200">{dept.name}</td>
                    <td className="px-4 py-3 font-mono text-zinc-600 hidden sm:table-cell">{dept.uuid}</td>
                    <td className="px-4 py-3 text-zinc-500 hidden md:table-cell">
                      {new Date(dept.created_at).toLocaleDateString("pt-BR")}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-3 justify-end">
                        <button
                          onClick={() => startEdit(dept)}
                          className="text-blue-400 hover:text-blue-300 transition-colors"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => { setConfirmDelete(dept); setError(""); }}
                          className="text-red-500 hover:text-red-400 transition-colors"
                        >
                          Excluir
                        </button>
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal de confirmação de exclusão */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 w-full max-w-sm shadow-2xl">
            <h3 className="text-sm font-semibold text-zinc-100 mb-2">Excluir departamento</h3>
            <p className="text-xs text-zinc-400 mb-5">
              Tem certeza que deseja excluir{" "}
              <span className="font-medium text-zinc-200">{confirmDelete.name}</span>?
              Esta ação não pode ser desfeita.
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
