import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { buildApiUrl } from "@/lib/api";

interface KbArticleDetail {
  id: string;
  slug: string;
  title: string;
  tags: string[];
  trust_level: number;
  created_at: string;
  body_markdown: string;
}

const TZ = "America/Sao_Paulo";
function fmtDate(s: string) {
  return new Date(s).toLocaleDateString("pt-BR", { timeZone: TZ, day: "2-digit", month: "long", year: "numeric" });
}

export default async function KbArticlePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const cookieStore = await cookies();
  const session = cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) notFound();

  let article: KbArticleDetail | null = null;
  try {
    const res = await fetch(buildApiUrl(`/api/v1/kb/articles/${slug}`), {
      headers: { Cookie: `${session.name}=${session.value}` },
      cache: "no-store",
    });
    if (res.ok) article = await res.json() as KbArticleDetail;
  } catch { /* ignore */ }

  if (!article) notFound();

  return (
    <div className="p-5 max-w-3xl space-y-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          {article.tags.map((tag) => (
            <span key={tag} className="text-[11px] bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded">{tag}</span>
          ))}
        </div>
        <h1 className="text-lg font-semibold text-zinc-100">{article.title}</h1>
        <p className="text-xs text-zinc-500 mt-1">Publicado em {fmtDate(article.created_at)}</p>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
        <pre className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed font-sans">
          {article.body_markdown}
        </pre>
      </div>

      <a href="/kb" className="inline-block text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
        ← Voltar para KB
      </a>
    </div>
  );
}
