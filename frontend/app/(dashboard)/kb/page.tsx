import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { buildApiUrl } from "@/lib/api";

interface KbArticleItem {
  id: string;
  slug: string;
  title: string;
  tags: string[];
  trust_level: string;
  created_at: string;
}

const TZ = "America/Sao_Paulo";
function fmtDate(s: string) {
  return new Date(s).toLocaleDateString("pt-BR", { timeZone: TZ });
}

const TRUST_LABEL: Record<string, string> = {
  internal_published: "publicado",
  internal_draft:     "rascunho",
  internal_only:      "interno",
  external_doc:       "externo",
};
const TRUST_COLOR: Record<string, string> = {
  internal_published: "bg-green-500/15 text-green-400",
  internal_draft:     "bg-zinc-500/15 text-zinc-400",
  internal_only:      "bg-blue-500/15 text-blue-400",
  external_doc:       "bg-orange-500/15 text-orange-400",
};

export default async function KbPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) redirect("/login");

  let articles: KbArticleItem[] = [];
  try {
    const res = await fetch(buildApiUrl("/api/v1/kb/articles"), {
      headers: { Cookie: `${session.name}=${session.value}` },
      cache: "no-store",
    });
    if (res.ok) articles = await res.json() as KbArticleItem[];
  } catch { /* ignore */ }

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-semibold text-zinc-100">Base de Conhecimento</h1>
        <span className="text-xs text-zinc-500">{articles.length} artigos</span>
      </div>

      {articles.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg py-12 text-center">
          <p className="text-sm text-zinc-500">Nenhum artigo encontrado.</p>
        </div>
      ) : (
        <div className="grid gap-2">
          {articles.map((a) => (
            <a
              key={a.id}
              href={`/kb/${a.slug}`}
              className="bg-zinc-900 border border-zinc-800 hover:border-zinc-600 rounded-lg px-4 py-3 transition-colors group"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-zinc-200 group-hover:text-white truncate">{a.title}</p>
                  <div className="flex flex-wrap items-center gap-2 mt-1.5">
                    {a.tags.slice(0, 4).map((tag) => (
                      <span key={tag} className="text-[11px] bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded">{tag}</span>
                    ))}
                    {a.tags.length > 4 && (
                      <span className="text-[11px] text-zinc-600">+{a.tags.length - 4}</span>
                    )}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                  <span className={`text-[11px] px-1.5 py-0.5 rounded font-medium ${TRUST_COLOR[a.trust_level] ?? "bg-zinc-500/15 text-zinc-400"}`}>
                    {TRUST_LABEL[a.trust_level] ?? a.trust_level}
                  </span>
                  <span className="text-[11px] text-zinc-600">{fmtDate(a.created_at)}</span>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
