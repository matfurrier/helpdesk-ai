"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface CsatItem {
  ticket_number: string;
  title: string;
  rating: number | null;
  comment: string | null;
  responded_at: string | null;
  closed_at: string | null;
}

const TZ = "America/Sao_Paulo";
function fmtDt(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function StarDisplay({ rating }: { rating: number | null }) {
  if (rating === null) return <span className="text-zinc-600 text-xs">sem nota</span>;
  return (
    <span className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= rating ? "text-yellow-400" : "text-zinc-700"}>★</span>
      ))}
    </span>
  );
}

export default function AdminReportsPage() {
  const router = useRouter();
  const [csat, setCsat] = useState<CsatItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [csvLoading, setCsvLoading] = useState(false);
  const [error, setError] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  async function loadCsat() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo + "T23:59:59");
      const res = await fetch("/api/v1/admin/reports/csat?" + params.toString());
      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) { setError("Erro ao carregar CSAT"); return; }
      setCsat(await res.json() as CsatItem[]);
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void loadCsat(); }, []);

  async function handleExportCsv() {
    setCsvLoading(true);
    try {
      const params = new URLSearchParams();
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo + "T23:59:59");
      const res = await fetch("/api/v1/admin/reports/tickets?" + params.toString());
      if (!res.ok) { setError("Erro ao exportar"); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "tickets.csv";
      a.click();
      URL.revokeObjectURL(url);
    } finally { setCsvLoading(false); }
  }

  const avgRating = csat.filter((c) => c.rating !== null).reduce((s, c) => s + (c.rating ?? 0), 0) /
    (csat.filter((c) => c.rating !== null).length || 1);

  return (
    <div className="p-5 max-w-5xl">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-zinc-100">Relatórios</h2>
      </div>

      {error && <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>}

      <div className="flex items-end gap-3 mb-5 flex-wrap">
        <div>
          <label className="block text-[11px] text-zinc-500 mb-1">De</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500"
          />
        </div>
        <div>
          <label className="block text-[11px] text-zinc-500 mb-1">Até</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500"
          />
        </div>
        <button
          onClick={() => void loadCsat()}
          disabled={loading}
          className="px-3 py-1.5 bg-zinc-800 text-zinc-200 text-xs rounded-md hover:bg-zinc-700 transition-colors disabled:opacity-50"
        >
          {loading ? "Filtrando..." : "Filtrar"}
        </button>
        <button
          onClick={() => void handleExportCsv()}
          disabled={csvLoading}
          className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {csvLoading ? "Exportando..." : "Exportar Chamados CSV"}
        </button>
      </div>

      {/* CSAT summary */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-[11px] text-zinc-500 uppercase tracking-wide">Avaliações</p>
          <p className="text-2xl font-bold text-zinc-100 mt-1">{csat.length}</p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-[11px] text-zinc-500 uppercase tracking-wide">Responderam</p>
          <p className="text-2xl font-bold text-zinc-100 mt-1">
            {csat.filter((c) => c.rating !== null).length}
          </p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-[11px] text-zinc-500 uppercase tracking-wide">Média</p>
          <p className="text-2xl font-bold text-zinc-100 mt-1">
            {csat.filter((c) => c.rating !== null).length > 0 ? avgRating.toFixed(1) : "—"}
          </p>
        </div>
      </div>

      {/* CSAT table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-zinc-800">
          <h3 className="text-xs font-medium text-zinc-400">Pesquisas de Satisfação (CSAT)</h3>
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500">
              <th className="text-left px-4 py-3 font-medium">Chamado</th>
              <th className="text-left px-4 py-3 font-medium">Nota</th>
              <th className="text-left px-4 py-3 font-medium">Comentário</th>
              <th className="text-left px-4 py-3 font-medium">Respondido em</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {csat.map((item, i) => (
              <tr key={i} className="hover:bg-zinc-800/30 transition-colors">
                <td className="px-4 py-3">
                  <div className="font-mono text-zinc-400">{item.ticket_number}</div>
                  <div className="text-zinc-300 mt-0.5 truncate max-w-48">{item.title}</div>
                </td>
                <td className="px-4 py-3">
                  <StarDisplay rating={item.rating} />
                </td>
                <td className="px-4 py-3 text-zinc-400 max-w-xs">
                  {item.comment ? (
                    <span className="italic">{item.comment}</span>
                  ) : (
                    <span className="text-zinc-600">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-zinc-400">{fmtDt(item.responded_at)}</td>
              </tr>
            ))}
            {csat.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-zinc-600">
                  Nenhuma avaliação no período
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
