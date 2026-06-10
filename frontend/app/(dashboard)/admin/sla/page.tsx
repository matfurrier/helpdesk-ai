"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface SlaEntry {
  priority: string;
  first_response_hours: number;
  resolution_hours: number;
  description: string | null;
}

const PRIORITY_LABEL: Record<string, string> = {
  urgent: "Urgente",
  high: "Alta",
  normal: "Normal",
  low: "Baixa",
};

const PRIORITY_COLOR: Record<string, string> = {
  urgent: "bg-red-500/15 text-red-400",
  high: "bg-orange-500/15 text-orange-400",
  normal: "bg-blue-500/15 text-blue-400",
  low: "bg-zinc-500/15 text-zinc-400",
};

async function getCsrfHeaders(): Promise<HeadersInit> {
  await fetch("/api/v1/auth/csrf");
  const csrf = document.cookie.split("; ").find((c) => c.startsWith("csrf_token="))?.split("=")[1] ?? "";
  return { "Content-Type": "application/json", "X-CSRF-Token": csrf };
}

export default function AdminSlaPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<SlaEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editFrh, setEditFrh] = useState(0);
  const [editRh, setEditRh] = useState(0);
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/admin/sla");
      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) { setError("Erro ao carregar SLA"); return; }
      setEntries(await res.json() as SlaEntry[]);
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, []);

  function startEdit(entry: SlaEntry) {
    setEditing(entry.priority);
    setEditFrh(entry.first_response_hours);
    setEditRh(entry.resolution_hours);
    setSuccess("");
    setError("");
  }

  async function handleSave(priority: string) {
    setSaving(true);
    try {
      const headers = await getCsrfHeaders();
      const res = await fetch(`/api/v1/admin/sla/${priority}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ first_response_hours: editFrh, resolution_hours: editRh }),
      });
      if (!res.ok) {
        const err = await res.json() as { detail?: string };
        setError(err.detail ?? "Erro ao salvar SLA");
        return;
      }
      setEditing(null);
      setSuccess("SLA atualizado com sucesso");
      await load();
    } finally { setSaving(false); }
  }

  if (loading) return <div className="p-6 text-zinc-500 text-sm">Carregando...</div>;

  return (
    <div className="p-5 max-w-2xl">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-zinc-100">Configuração de SLA</h2>
        <p className="text-xs text-zinc-500 mt-0.5">
          Prazos de primeira resposta e resolução por prioridade. Aplicados em novos chamados.
        </p>
      </div>

      {error && <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>}
      {success && <div className="mb-3 px-3 py-2 bg-green-500/10 text-green-400 rounded text-xs">{success}</div>}

      <div className="space-y-3">
        {entries.map((entry) => (
          <div
            key={entry.priority}
            className="bg-zinc-900 border border-zinc-800 rounded-lg p-4"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${PRIORITY_COLOR[entry.priority] ?? ""}`}>
                  {PRIORITY_LABEL[entry.priority] ?? entry.priority}
                </span>
                {entry.description && (
                  <span className="text-xs text-zinc-500">{entry.description}</span>
                )}
              </div>

              {editing !== entry.priority && (
                <button
                  onClick={() => startEdit(entry)}
                  className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  Editar
                </button>
              )}
            </div>

            {editing === entry.priority ? (
              <div className="mt-4 space-y-3">
                <div className="flex gap-6">
                  <div>
                    <label className="block text-[11px] font-medium text-zinc-500 mb-1">
                      1ª Resposta (horas)
                    </label>
                    <input
                      type="number"
                      min={1}
                      value={editFrh}
                      onChange={(e) => setEditFrh(parseInt(e.target.value) || 1)}
                      className="w-24 bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-200 text-center focus:outline-none focus:border-zinc-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-zinc-500 mb-1">
                      Resolução (horas)
                    </label>
                    <input
                      type="number"
                      min={1}
                      value={editRh}
                      onChange={(e) => setEditRh(parseInt(e.target.value) || 1)}
                      className="w-24 bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-200 text-center focus:outline-none focus:border-zinc-500"
                    />
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setEditing(null)}
                    className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    onClick={() => void handleSave(entry.priority)}
                    disabled={saving}
                    className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
                  >
                    {saving ? "Salvando..." : "Salvar"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-3 flex gap-8">
                <div>
                  <p className="text-[11px] text-zinc-600">1ª Resposta</p>
                  <p className="text-sm font-medium text-zinc-200 mt-0.5">
                    {entry.first_response_hours}h
                  </p>
                </div>
                <div>
                  <p className="text-[11px] text-zinc-600">Resolução</p>
                  <p className="text-sm font-medium text-zinc-200 mt-0.5">
                    {entry.resolution_hours}h
                  </p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
