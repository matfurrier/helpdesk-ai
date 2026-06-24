"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface Category {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
}

export default function AdminCategoriesPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editSort, setEditSort] = useState(0);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/admin/categories");
      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) { setError("Erro ao carregar categorias"); return; }
      setCategories(await res.json() as Category[]);
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, []);

  async function handleToggle(cat: Category) {
    setSaving(cat.id);
    try {
      const headers = { "Content-Type": "application/json" };
      await fetch(`/api/v1/admin/categories/${cat.id}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ is_active: !cat.is_active }),
      });
      await load();
    } finally { setSaving(null); }
  }

  function startEdit(cat: Category) {
    setEditing(cat.id);
    setEditName(cat.name);
    setEditDesc(cat.description ?? "");
    setEditSort(cat.sort_order);
  }

  async function handleSaveEdit(cat: Category) {
    setSaving(cat.id + ":edit");
    try {
      const headers = { "Content-Type": "application/json" };
      const res = await fetch(`/api/v1/admin/categories/${cat.id}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ name: editName, description: editDesc || null, sort_order: editSort }),
      });
      if (!res.ok) { setError("Erro ao salvar"); return; }
      setEditing(null);
      await load();
    } finally { setSaving(null); }
  }

  async function handleCreate() {
    setCreating(true);
    setError("");
    try {
      const headers = { "Content-Type": "application/json" };
      const slug = newSlug || newName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
      const res = await fetch("/api/v1/admin/categories", {
        method: "POST",
        headers,
        body: JSON.stringify({ slug, name: newName, description: newDesc || null }),
      });
      if (!res.ok) {
        const err = await res.json() as { detail?: string };
        setError(err.detail ?? "Erro ao criar");
        return;
      }
      setNewName(""); setNewSlug(""); setNewDesc("");
      setShowForm(false);
      await load();
    } finally { setCreating(false); }
  }

  if (loading) return <div className="p-6 text-zinc-500 text-sm">Carregando...</div>;

  return (
    <div className="p-5 max-w-3xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">Categorias</h2>
          <p className="text-xs text-zinc-500 mt-0.5">{categories.length} categorias</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors"
        >
          + Nova Categoria
        </button>
      </div>

      {error && <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>}

      {showForm && (
        <div className="mb-4 bg-zinc-900 border border-zinc-700 rounded-lg p-4 space-y-3">
          <h3 className="text-xs font-medium text-zinc-400">Nova Categoria</h3>
          <div className="flex gap-3">
            <div className="flex-1">
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Nome"
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div className="flex-1">
              <input
                value={newSlug}
                onChange={(e) => setNewSlug(e.target.value)}
                placeholder="Slug (automático se vazio)"
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>
          </div>
          <input
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            placeholder="Descrição (opcional)"
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
          />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors">Cancelar</button>
            <button
              onClick={() => void handleCreate()}
              disabled={creating || !newName}
              className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {creating ? "Criando..." : "Criar"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500">
              <th className="text-left px-4 py-3 font-medium w-8">#</th>
              <th className="text-left px-4 py-3 font-medium">Nome</th>
              <th className="text-left px-4 py-3 font-medium">Descrição</th>
              <th className="text-center px-4 py-3 font-medium">Ativo</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {categories.map((cat) => (
              <tr key={cat.id} className="hover:bg-zinc-800/30 transition-colors">
                {editing === cat.id ? (
                  <>
                    <td className="px-4 py-3">
                      <input
                        type="number"
                        value={editSort}
                        onChange={(e) => setEditSort(parseInt(e.target.value) || 0)}
                        className="w-12 bg-zinc-800 border border-zinc-700 rounded px-1 py-1 text-zinc-200 text-center focus:outline-none"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-200 focus:outline-none focus:border-zinc-500"
                      />
                      <div className="font-mono text-zinc-600 mt-0.5">{cat.slug}</div>
                    </td>
                    <td className="px-4 py-3">
                      <input
                        value={editDesc}
                        onChange={(e) => setEditDesc(e.target.value)}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-200 focus:outline-none focus:border-zinc-500"
                      />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={cat.is_active ? "text-green-400" : "text-zinc-600"}>
                        {cat.is_active ? "✓" : "✗"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2 justify-end">
                        <button onClick={() => setEditing(null)} className="text-zinc-500 hover:text-zinc-300 transition-colors">Cancelar</button>
                        <button
                          onClick={() => void handleSaveEdit(cat)}
                          disabled={saving === cat.id + ":edit"}
                          className="text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50"
                        >
                          {saving === cat.id + ":edit" ? "..." : "Salvar"}
                        </button>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-3 text-zinc-500">{cat.sort_order}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-zinc-200">{cat.name}</div>
                      <div className="font-mono text-zinc-600 mt-0.5">{cat.slug}</div>
                    </td>
                    <td className="px-4 py-3 text-zinc-400">{cat.description ?? "—"}</td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => void handleToggle(cat)}
                        disabled={saving === cat.id}
                        className={`px-2 py-0.5 rounded-full text-[11px] transition-colors disabled:opacity-50 ${
                          cat.is_active
                            ? "bg-green-500/15 text-green-400 hover:bg-red-500/15 hover:text-red-400"
                            : "bg-zinc-700/30 text-zinc-500 hover:bg-green-500/15 hover:text-green-400"
                        }`}
                      >
                        {cat.is_active ? "Ativo" : "Inativo"}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => startEdit(cat)}
                        className="text-blue-400 hover:text-blue-300 transition-colors"
                      >
                        Editar
                      </button>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
