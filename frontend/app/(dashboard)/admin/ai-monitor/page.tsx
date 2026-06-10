"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface AiLogItem {
  id: string;
  prompt_key: string;
  provider: string;
  model_name: string;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number | null;
  http_status: number | null;
  guardrail_flags: string[];
  was_fallback: boolean;
  validation_status: string;
  created_at: string;
}

interface PageData {
  items: AiLogItem[];
  total: number;
  page: number;
  page_size: number;
}

const TZ = "America/Sao_Paulo";
function fmtDt(s: string) {
  return new Date(s).toLocaleString("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function AiMonitorPage() {
  const router = useRouter();
  const [data, setData] = useState<PageData | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(p: number) {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/admin/ai-monitor?page=${p}&page_size=25`);
      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) { setError("Erro ao carregar logs"); return; }
      setData(await res.json() as PageData);
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(page); }, [page]);

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <div className="p-5 max-w-6xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">Monitor IA</h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            {data ? `${data.total} chamadas no total` : "Carregando..."}
          </p>
        </div>
        <button onClick={() => void load(page)} className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
          Atualizar
        </button>
      </div>

      {error && <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>}

      {/* Stats bar */}
      {data && data.items.length > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
            <p className="text-[11px] text-zinc-500">Total (página)</p>
            <p className="text-lg font-bold text-zinc-100 mt-0.5">{data.items.length}</p>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
            <p className="text-[11px] text-zinc-500">Tokens entrada</p>
            <p className="text-lg font-bold text-zinc-100 mt-0.5">
              {data.items.reduce((s, i) => s + (i.input_tokens ?? 0), 0).toLocaleString()}
            </p>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
            <p className="text-[11px] text-zinc-500">Tokens saída</p>
            <p className="text-lg font-bold text-zinc-100 mt-0.5">
              {data.items.reduce((s, i) => s + (i.output_tokens ?? 0), 0).toLocaleString()}
            </p>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
            <p className="text-[11px] text-zinc-500">Latência média</p>
            <p className="text-lg font-bold text-zinc-100 mt-0.5">
              {data.items.filter((i) => i.latency_ms).length > 0
                ? Math.round(data.items.reduce((s, i) => s + (i.latency_ms ?? 0), 0) / data.items.filter((i) => i.latency_ms).length) + "ms"
                : "—"}
            </p>
          </div>
        </div>
      )}

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500">
              <th className="text-left px-3 py-3 font-medium">Data</th>
              <th className="text-left px-3 py-3 font-medium">Prompt</th>
              <th className="text-left px-3 py-3 font-medium">Modelo</th>
              <th className="text-right px-3 py-3 font-medium">In</th>
              <th className="text-right px-3 py-3 font-medium">Out</th>
              <th className="text-right px-3 py-3 font-medium">Latência</th>
              <th className="text-center px-3 py-3 font-medium">HTTP</th>
              <th className="text-left px-3 py-3 font-medium">Flags</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-zinc-600">Carregando...</td></tr>
            ) : data?.items.map((item) => (
              <tr key={item.id} className={`hover:bg-zinc-800/30 transition-colors ${item.guardrail_flags.length > 0 ? "bg-orange-500/5" : ""}`}>
                <td className="px-3 py-2.5 text-zinc-500 whitespace-nowrap">{fmtDt(item.created_at)}</td>
                <td className="px-3 py-2.5">
                  <span className="font-mono text-zinc-300">{item.prompt_key}</span>
                  {item.was_fallback && (
                    <span className="ml-1 px-1 py-0.5 rounded bg-orange-500/15 text-orange-400 text-[10px]">fallback</span>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  <div className="text-zinc-300">{item.provider}</div>
                  <div className="text-zinc-600 font-mono text-[10px] truncate max-w-32">{item.model_name}</div>
                </td>
                <td className="px-3 py-2.5 text-right text-zinc-400 tabular-nums">
                  {item.input_tokens?.toLocaleString() ?? "—"}
                </td>
                <td className="px-3 py-2.5 text-right text-zinc-400 tabular-nums">
                  {item.output_tokens?.toLocaleString() ?? "—"}
                </td>
                <td className="px-3 py-2.5 text-right text-zinc-400 tabular-nums">
                  {item.latency_ms ? `${item.latency_ms}ms` : "—"}
                </td>
                <td className="px-3 py-2.5 text-center">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                    item.http_status === 200 ? "text-green-400" :
                    item.http_status && item.http_status >= 500 ? "text-red-400" :
                    "text-zinc-400"
                  }`}>
                    {item.http_status ?? "—"}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  {item.guardrail_flags.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {item.guardrail_flags.map((f) => (
                        <span key={f} className="px-1 py-0.5 rounded bg-orange-500/20 text-orange-400 text-[10px]">{f}</span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-zinc-700">—</span>
                  )}
                </td>
              </tr>
            ))}
            {!loading && data?.items.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-zinc-600">Nenhuma chamada registrada</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-zinc-500">
            Página {page} de {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1 || loading}
              className="px-3 py-1.5 text-xs bg-zinc-800 text-zinc-300 rounded hover:bg-zinc-700 transition-colors disabled:opacity-40"
            >
              Anterior
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages || loading}
              className="px-3 py-1.5 text-xs bg-zinc-800 text-zinc-300 rounded hover:bg-zinc-700 transition-colors disabled:opacity-40"
            >
              Próxima
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
