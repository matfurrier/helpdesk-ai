"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

interface ArticleDetail {
  id: string;
  slug: string;
  title: string;
  tags: string[];
  trust_level: string;
  is_archived: boolean;
  chunk_count: number;
  created_at: string;
  body_markdown: string;
}

const TRUST_LEVELS = ["internal_published", "internal_draft", "internal_only", "external_doc"];
const TRUST_LABEL: Record<string, string> = {
  internal_published: "Publicado",
  internal_draft: "Rascunho",
  internal_only: "Interno",
  external_doc: "Externo",
};

export default function KbEditPage() {
  const params = useParams();
  const router = useRouter();
  const slug = params.slug as string;
  const isNew = slug === "new";

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tagsRaw, setTagsRaw] = useState("");
  const [trust, setTrust] = useState("internal_draft");
  const [articleSlug, setArticleSlug] = useState("");
  const [chunkCount, setChunkCount] = useState(0);

  useEffect(() => {
    if (isNew) return;
    setLoading(true);
    fetch(`/api/v1/admin/kb/articles/${slug}`)
      .then(async (res) => {
        if (res.status === 401) { router.push("/login"); return; }
        if (res.status === 403) { setError("Acesso negado"); return; }
        if (!res.ok) { setError("Artigo não encontrado"); return; }
        const data = await res.json() as ArticleDetail;
        setTitle(data.title);
        setBody(data.body_markdown);
        setTagsRaw(data.tags.join(", "));
        setTrust(data.trust_level);
        setArticleSlug(data.slug);
        setChunkCount(data.chunk_count);
      })
      .catch(() => setError("Erro de rede"))
      .finally(() => setLoading(false));
  }, [slug, isNew, router]);

  async function handleSave() {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const headers = { "Content-Type": "application/json" };
      const tags = tagsRaw.split(",").map((t) => t.trim()).filter(Boolean);

      if (isNew) {
        const generatedSlug = articleSlug || title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
        const res = await fetch("/api/v1/admin/kb/articles", {
          method: "POST",
          headers,
          body: JSON.stringify({ slug: generatedSlug, title, body_markdown: body, tags, trust_level: trust }),
        });
        if (!res.ok) {
          const err = await res.json() as { detail?: string };
          setError(err.detail ?? "Erro ao criar artigo");
          return;
        }
        const created = await res.json() as { slug: string; chunks_created: number };
        setSuccess(`Artigo criado com ${created.chunks_created} chunks. Redirecionando...`);
        setTimeout(() => router.push(`/admin/kb/${created.slug}`), 1200);
      } else {
        const res = await fetch(`/api/v1/admin/kb/articles/${slug}`, {
          method: "PATCH",
          headers,
          body: JSON.stringify({ title, body_markdown: body, tags, trust_level: trust }),
        });
        if (!res.ok) {
          const err = await res.json() as { detail?: string };
          setError(err.detail ?? "Erro ao salvar");
          return;
        }
        const updated = await res.json() as ArticleDetail;
        setChunkCount(updated.chunk_count);
        setSuccess(`Salvo e re-ingerido: ${updated.chunk_count} chunks`);
      }
    } finally { setSaving(false); }
  }

  if (loading) return <div className="p-6 text-zinc-500 text-sm">Carregando...</div>;

  return (
    <div className="p-5 max-w-3xl">
      <div className="flex items-center gap-3 mb-5">
        <Link href="/admin/kb" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
          ← Base de Conhecimento
        </Link>
        <span className="text-zinc-700">/</span>
        <span className="text-xs text-zinc-400">{isNew ? "Novo Artigo" : title}</span>
      </div>

      {!isNew && (
        <div className="mb-4 px-3 py-2 bg-zinc-900 border border-zinc-800 rounded text-xs text-zinc-500 flex gap-4">
          <span>Slug: <span className="font-mono text-zinc-400">{articleSlug}</span></span>
          <span>Chunks RAG: <span className="text-zinc-400">{chunkCount}</span></span>
        </div>
      )}

      {error && <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>}
      {success && <div className="mb-3 px-3 py-2 bg-green-500/10 text-green-400 rounded text-xs">{success}</div>}

      <div className="space-y-4">
        {isNew && (
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1">Slug (URL)</label>
            <input
              value={articleSlug}
              onChange={(e) => setArticleSlug(e.target.value)}
              placeholder="ex: vpn-configuracao (gerado automaticamente se vazio)"
              className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            />
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-zinc-400 mb-1">Título</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Título do artigo"
            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
          />
        </div>

        <div className="flex gap-4">
          <div className="flex-1">
            <label className="block text-xs font-medium text-zinc-400 mb-1">Tags (separadas por vírgula)</label>
            <input
              value={tagsRaw}
              onChange={(e) => setTagsRaw(e.target.value)}
              placeholder="vpn, acesso, senha"
              className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1">Nível de confiança</label>
            <select
              value={trust}
              onChange={(e) => setTrust(e.target.value)}
              className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500"
            >
              {TRUST_LEVELS.map((t) => (
                <option key={t} value={t}>{TRUST_LABEL[t]}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-400 mb-1">
            Conteúdo (Markdown)
          </label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={20}
            placeholder="# Título&#10;&#10;Conteúdo em Markdown..."
            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 font-mono leading-relaxed resize-y"
          />
          <p className="mt-1 text-[11px] text-zinc-600">
            Ao salvar, o conteúdo é re-ingerido automaticamente na base RAG (embeddings atualizados).
          </p>
        </div>

        <div className="flex justify-end">
          <button
            onClick={() => void handleSave()}
            disabled={saving || !title || !body}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Salvando..." : isNew ? "Criar Artigo" : "Salvar e Re-ingerir"}
          </button>
        </div>
      </div>
    </div>
  );
}
