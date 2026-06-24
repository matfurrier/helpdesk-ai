"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface KbArticle {
  id: string;
  slug: string;
  title: string;
  tags: string[];
  trust_level: string;
  is_archived: boolean;
  chunk_count: number;
  created_at: string;
}

const TRUST_LABEL: Record<string, string> = {
  internal_published: "Publicado",
  internal_draft: "Rascunho",
  internal_only: "Interno",
  external_doc: "Externo",
};

const TRUST_COLOR: Record<string, string> = {
  internal_published: "bg-green-500/15 text-green-400",
  internal_draft: "bg-yellow-500/15 text-yellow-400",
  internal_only: "bg-blue-500/15 text-blue-400",
  external_doc: "bg-purple-500/15 text-purple-400",
};

export default function AdminKbPage() {
  const router = useRouter();
  const [articles, setArticles] = useState<KbArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/admin/kb/articles");
      if (res.status === 401) { router.push("/login"); return; }
      if (res.status === 403) { setError("Acesso negado"); return; }
      if (!res.ok) { setError("Erro ao carregar artigos"); return; }
      setArticles(await res.json() as KbArticle[]);
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, []);

  async function handleArchive(slug: string) {
    setActionLoading(slug + ":archive");
    try {
      const headers = { "Content-Type": "application/json" };
      const res = await fetch(`/api/v1/admin/kb/articles/${slug}/archive`, { method: "POST", headers });
      if (res.ok) await load();
      else setError("Erro ao arquivar artigo");
    } finally { setActionLoading(null); }
  }

  async function handleRestore(slug: string) {
    setActionLoading(slug + ":restore");
    try {
      const headers = { "Content-Type": "application/json" };
      const res = await fetch(`/api/v1/admin/kb/articles/${slug}/restore`, { method: "POST", headers });
      if (res.ok) await load();
      else setError("Erro ao restaurar artigo");
    } finally { setActionLoading(null); }
  }

  if (loading) return <div className="p-6 text-zinc-500 text-sm">Carregando...</div>;

  return (
    <div className="p-5 max-w-5xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">Base de Conhecimento</h2>
          <p className="text-xs text-zinc-500 mt-0.5">{articles.length} artigos</p>
        </div>
        <Link
          href="/admin/kb/new"
          className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors"
        >
          + Novo Artigo
        </Link>
      </div>

      {error && (
        <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>
      )}

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500">
              <th className="text-left px-4 py-3 font-medium">Título</th>
              <th className="text-left px-4 py-3 font-medium">Status</th>
              <th className="text-left px-4 py-3 font-medium">Chunks</th>
              <th className="text-left px-4 py-3 font-medium">Tags</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {articles.map((a) => (
              <tr key={a.id} className={`hover:bg-zinc-800/30 transition-colors ${a.is_archived ? "opacity-50" : ""}`}>
                <td className="px-4 py-3">
                  <div className="font-medium text-zinc-200">{a.title}</div>
                  <div className="text-zinc-500 font-mono mt-0.5">{a.slug}</div>
                </td>
                <td className="px-4 py-3">
                  {a.is_archived ? (
                    <span className="px-2 py-0.5 rounded-full bg-zinc-600/30 text-zinc-500">Arquivado</span>
                  ) : (
                    <span className={`px-2 py-0.5 rounded-full ${TRUST_COLOR[a.trust_level] ?? "bg-zinc-500/15 text-zinc-400"}`}>
                      {TRUST_LABEL[a.trust_level] ?? a.trust_level}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-zinc-400">{a.chunk_count}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {a.tags.slice(0, 3).map((t) => (
                      <span key={t} className="px-1.5 py-0.5 rounded bg-zinc-700/60 text-zinc-400">{t}</span>
                    ))}
                    {a.tags.length > 3 && <span className="text-zinc-600">+{a.tags.length - 3}</span>}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2 justify-end">
                    {!a.is_archived && (
                      <Link
                        href={`/admin/kb/${a.slug}`}
                        className="text-blue-400 hover:text-blue-300 transition-colors"
                      >
                        Editar
                      </Link>
                    )}
                    {a.is_archived ? (
                      <button
                        onClick={() => void handleRestore(a.slug)}
                        disabled={actionLoading === a.slug + ":restore"}
                        className="text-green-400 hover:text-green-300 transition-colors disabled:opacity-50"
                      >
                        {actionLoading === a.slug + ":restore" ? "..." : "Restaurar"}
                      </button>
                    ) : (
                      <button
                        onClick={() => void handleArchive(a.slug)}
                        disabled={actionLoading === a.slug + ":archive"}
                        className="text-red-400 hover:text-red-300 transition-colors disabled:opacity-50"
                      >
                        {actionLoading === a.slug + ":archive" ? "..." : "Arquivar"}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {articles.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-zinc-600">Nenhum artigo</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
