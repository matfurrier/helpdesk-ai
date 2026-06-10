import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { buildApiUrl } from "@/lib/api";

interface KbArticleDetail {
  id: string;
  slug: string;
  title: string;
  tags: string[];
  trust_level: string;
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

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5 space-y-3">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ children }) => <h1 className="text-base font-bold text-zinc-100 mt-4 mb-2 first:mt-0">{children}</h1>,
            h2: ({ children }) => <h2 className="text-sm font-semibold text-zinc-100 mt-4 mb-2 first:mt-0">{children}</h2>,
            h3: ({ children }) => <h3 className="text-sm font-semibold text-zinc-200 mt-3 mb-1">{children}</h3>,
            p:  ({ children }) => <p className="text-sm text-zinc-300 leading-relaxed mb-3">{children}</p>,
            strong: ({ children }) => <strong className="font-semibold text-zinc-100">{children}</strong>,
            em: ({ children }) => <em className="italic text-zinc-300">{children}</em>,
            ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-3 text-sm text-zinc-300">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-3 text-sm text-zinc-300">{children}</ol>,
            li: ({ children }) => <li className="text-zinc-300 leading-relaxed">{children}</li>,
            code: ({ children, className }) => {
              const isBlock = className?.includes("language-");
              return isBlock
                ? <code className="block bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-[13px] text-blue-300 font-mono overflow-x-auto mb-3">{children}</code>
                : <code className="bg-zinc-800 text-blue-300 px-1.5 py-0.5 rounded text-[13px] font-mono">{children}</code>;
            },
            pre: ({ children }) => <pre className="mb-3">{children}</pre>,
            blockquote: ({ children }) => <blockquote className="border-l-2 border-zinc-600 pl-3 italic text-zinc-400 mb-3">{children}</blockquote>,
            hr: () => <hr className="border-zinc-800 my-4" />,
            a: ({ href, children }) => <a href={href} className="text-blue-400 hover:underline">{children}</a>,
            table: ({ children }) => <div className="overflow-x-auto mb-3"><table className="w-full text-sm border border-zinc-700 rounded">{children}</table></div>,
            thead: ({ children }) => <thead className="bg-zinc-800 text-zinc-300">{children}</thead>,
            th: ({ children }) => <th className="px-3 py-1.5 text-left font-medium border-b border-zinc-700">{children}</th>,
            td: ({ children }) => <td className="px-3 py-1.5 text-zinc-300 border-b border-zinc-800">{children}</td>,
          }}
        >
          {article.body_markdown}
        </ReactMarkdown>
      </div>

      <Link href="/kb" className="inline-block text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
        ← Voltar para KB
      </Link>
    </div>
  );
}
