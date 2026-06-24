"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";

interface AssetHistoryItem {
  id: string;
  action: string;
  holder_name: string | null;
  holder_dept: string | null;
  changed_by: string;
  changed_at: string;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  notes: string | null;
}

interface AssetDetail {
  id: string;
  asset_tag: string | null;
  asset_type: string;
  brand: string | null;
  model: string;
  serial_number: string | null;
  status: string;
  holder_id: string | null;
  holder_name: string | null;
  holder_dept: string | null;
  acquired_at: string | null;
  warranty_until: string | null;
  specs: Record<string, string>;
  compliance: Record<string, boolean>;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  history: AssetHistoryItem[];
}

interface SecurityUser {
  uuid: string;
  name: string;
  email: string;
}

const TYPE_LABELS: Record<string, string> = {
  notebook: "Notebook",
  smartphone: "Smartphone",
  tablet: "Tablet",
  other: "Outro",
};

const STATUS_LABELS: Record<string, string> = {
  active: "Ativo",
  maintenance: "Manutenção",
  retired: "Desativado",
  lost: "Extraviado",
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-500/15 text-green-400",
  maintenance: "bg-yellow-500/15 text-yellow-400",
  retired: "bg-zinc-700/30 text-zinc-500",
  lost: "bg-red-500/15 text-red-400",
};

const ACTION_LABELS: Record<string, string> = {
  created: "Cadastrado",
  assigned: "Atribuído",
  returned: "Devolvido",
  status_changed: "Status alterado",
  updated: "Atualizado",
};


export default function AssetDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const assetId = params.id;

  const [asset, setAsset] = useState<AssetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // Edit mode fields
  const [editing, setEditing] = useState(false);
  const [editTag, setEditTag] = useState("");
  const [editBrand, setEditBrand] = useState("");
  const [editModel, setEditModel] = useState("");
  const [editSerial, setEditSerial] = useState("");
  const [editStatus, setEditStatus] = useState("");
  const [editAcquired, setEditAcquired] = useState("");
  const [editWarranty, setEditWarranty] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editSpecs, setEditSpecs] = useState<Record<string, string>>({});
  const [editCompliance, setEditCompliance] = useState<Record<string, boolean>>({});

  // Assign modal
  const [showAssign, setShowAssign] = useState(false);
  const [users, setUsers] = useState<SecurityUser[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [selectedUser, setSelectedUser] = useState("");
  const [assignNotes, setAssignNotes] = useState("");
  const [assigning, setAssigning] = useState(false);

  // Return modal
  const [showReturn, setShowReturn] = useState(false);
  const [returnNotes, setReturnNotes] = useState("");
  const [returning, setReturning] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/v1/admin/assets/${assetId}`);
      if (res.status === 401) { router.push("/login"); return; }
      if (res.status === 404) { setError("Equipamento não encontrado"); return; }
      if (!res.ok) { setError("Erro ao carregar"); return; }
      const data = (await res.json()) as AssetDetail;
      setAsset(data);
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, [assetId]);

  function startEdit(a: AssetDetail) {
    setEditTag(a.asset_tag ?? "");
    setEditBrand(a.brand ?? "");
    setEditModel(a.model);
    setEditSerial(a.serial_number ?? "");
    setEditStatus(a.status);
    setEditAcquired(a.acquired_at?.slice(0, 10) ?? "");
    setEditWarranty(a.warranty_until?.slice(0, 10) ?? "");
    setEditNotes(a.notes ?? "");
    setEditSpecs({ ...a.specs });
    setEditCompliance({ ...a.compliance });
    setEditing(true);
  }

  async function handleSave() {
    if (!asset) return;
    setSaving(true);
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      const body: Record<string, unknown> = {
        asset_tag: editTag || null,
        brand: editBrand || null,
        model: editModel,
        serial_number: editSerial || null,
        status: editStatus,
        acquired_at: editAcquired || null,
        warranty_until: editWarranty || null,
        notes: editNotes || null,
        specs: editSpecs,
        compliance: editCompliance,
      };
      const res = await fetch(`/api/v1/admin/assets/${asset.id}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = (await res.json()) as { detail?: unknown };
        const detail = err.detail;
        const msg = typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? (detail as { msg?: string }[]).map((e) => e.msg ?? String(e)).join("; ")
            : "Erro ao salvar";
        setError(msg);
        return;
      }
      setEditing(false);
      await load();
    } finally { setSaving(false); }
  }

  async function loadUsers() {
    setLoadingUsers(true);
    try {
      const res = await fetch("/api/v1/admin/users");
      if (!res.ok) return;
      const data = (await res.json()) as { uuid: string; name: string; email: string }[];
      setUsers(data);
    } finally { setLoadingUsers(false); }
  }

  function openAssign() {
    setSelectedUser("");
    setAssignNotes("");
    setShowAssign(true);
    void loadUsers();
  }

  async function handleAssign() {
    if (!asset || !selectedUser) return;
    setAssigning(true);
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      const res = await fetch(`/api/v1/admin/assets/${asset.id}/assign`, {
        method: "POST",
        headers,
        body: JSON.stringify({ holder_id: selectedUser, notes: assignNotes || null }),
      });
      if (!res.ok) {
        const err = (await res.json()) as { detail?: unknown };
        const detail = err.detail;
        setError(typeof detail === "string" ? detail : Array.isArray(detail) ? (detail as { msg?: string }[]).map((e) => e.msg ?? String(e)).join("; ") : "Erro ao atribuir");
        return;
      }
      setShowAssign(false);
      await load();
    } finally { setAssigning(false); }
  }

  async function handleReturn() {
    if (!asset) return;
    setReturning(true);
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      const res = await fetch(`/api/v1/admin/assets/${asset.id}/return`, {
        method: "POST",
        headers,
        body: JSON.stringify({ notes: returnNotes || null }),
      });
      if (!res.ok) {
        const err = (await res.json()) as { detail?: unknown };
        const detail = err.detail;
        setError(typeof detail === "string" ? detail : Array.isArray(detail) ? (detail as { msg?: string }[]).map((e) => e.msg ?? String(e)).join("; ") : "Erro ao registrar devolução");
        return;
      }
      setShowReturn(false);
      await load();
    } finally { setReturning(false); }
  }

  async function handleRetire() {
    if (!asset) return;
    if (!confirm("Desativar este equipamento? O titular atual será removido.")) return;
    setSaving(true);
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      await fetch(`/api/v1/admin/assets/${asset.id}`, { method: "DELETE", headers });
      router.push("/admin/assets");
    } finally { setSaving(false); }
  }

  if (loading) return <div className="p-6 text-zinc-500 text-sm">Carregando...</div>;
  if (error && !asset) return <div className="p-6 text-red-400 text-sm">{error}</div>;
  if (!asset) return null;

  const specsEntries = Object.entries(asset.specs).filter(([, v]) => v);
  const complianceEntries = Object.entries(asset.compliance);

  return (
    <div className="p-5 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <button
            onClick={() => router.push("/admin/assets")}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors mb-2 flex items-center gap-1"
          >
            ← Patrimônio
          </button>
          <h2 className="text-base font-semibold text-zinc-100">
            {asset.brand ? `${asset.brand} ${asset.model}` : asset.model}
          </h2>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-zinc-500">{TYPE_LABELS[asset.asset_type] ?? asset.asset_type}</span>
            {asset.asset_tag && (
              <span className="font-mono text-xs text-zinc-400">#{asset.asset_tag}</span>
            )}
            <span className={`px-2 py-0.5 rounded-full text-[11px] ${STATUS_COLORS[asset.status] ?? "text-zinc-400"}`}>
              {STATUS_LABELS[asset.status] ?? asset.status}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {asset.status !== "retired" && (asset.holder_id || asset.holder_name) && (
            <button
              onClick={() => { setReturnNotes(""); setShowReturn(true); }}
              className="px-3 py-1.5 bg-zinc-800 text-zinc-300 text-xs rounded hover:bg-zinc-700 border border-zinc-700 transition-colors"
            >
              Devolver
            </button>
          )}
          {!editing && (
            <>
              <button
                onClick={() => startEdit(asset)}
                className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors"
              >
                Editar
              </button>
              {asset.status !== "retired" && (
                <>
                  <button
                    onClick={openAssign}
                    className="px-3 py-1.5 bg-zinc-800 text-zinc-300 text-xs rounded hover:bg-zinc-700 border border-zinc-700 transition-colors"
                  >
                    {asset.holder_id || asset.holder_name ? "Transferir" : "Atribuir"}
                  </button>
                  <button
                    onClick={() => void handleRetire()}
                    disabled={saving}
                    className="px-3 py-1.5 bg-zinc-800 text-red-400 text-xs rounded hover:bg-zinc-700 border border-zinc-700 transition-colors disabled:opacity-50"
                  >
                    Desativar
                  </button>
                </>
              )}
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Main info */}
        <div className="lg:col-span-2 space-y-4">
          {/* General */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-zinc-400 mb-3">Informações gerais</h3>
            {editing ? (
              <div className="grid grid-cols-2 gap-3">
                {([
                  ["Patrimônio / Placa", editTag, setEditTag, "mono"],
                  ["Marca", editBrand, setEditBrand, ""],
                  ["Modelo", editModel, setEditModel, ""],
                  ["Serial", editSerial, setEditSerial, "mono"],
                ] as [string, string, (v: string) => void, string][]).map(([label, val, setter, font]) => (
                  <div key={label}>
                    <label className="text-[11px] text-zinc-500 block mb-1">{label}</label>
                    <input
                      value={val}
                      onChange={(e) => setter(e.target.value)}
                      className={`w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500 ${font === "mono" ? "font-mono" : ""}`}
                    />
                  </div>
                ))}
                <div>
                  <label className="text-[11px] text-zinc-500 block mb-1">Status</label>
                  <select
                    value={editStatus}
                    onChange={(e) => setEditStatus(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500"
                  >
                    {Object.entries(STATUS_LABELS).map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[11px] text-zinc-500 block mb-1">Aquisição</label>
                  <input
                    type="date"
                    value={editAcquired}
                    onChange={(e) => setEditAcquired(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-zinc-500 block mb-1">Garantia até</label>
                  <input
                    type="date"
                    value={editWarranty}
                    onChange={(e) => setEditWarranty(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500"
                  />
                </div>
                <div className="col-span-2">
                  <label className="text-[11px] text-zinc-500 block mb-1">Observações</label>
                  <input
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500"
                  />
                </div>
              </div>
            ) : (
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                {[
                  ["Patrimônio", asset.asset_tag ?? "—"],
                  ["Marca", asset.brand ?? "—"],
                  ["Modelo", asset.model],
                  ["Serial", asset.serial_number ?? "—"],
                  ["Aquisição", asset.acquired_at?.slice(0, 10) ?? "—"],
                  ["Garantia até", asset.warranty_until?.slice(0, 10) ?? "—"],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-zinc-500">{k}</dt>
                    <dd className="text-zinc-200 font-medium mt-0.5">{v}</dd>
                  </div>
                ))}
                {asset.notes && (
                  <div className="col-span-2">
                    <dt className="text-zinc-500">Observações</dt>
                    <dd className="text-zinc-300 mt-0.5">{asset.notes}</dd>
                  </div>
                )}
              </dl>
            )}
          </div>

          {/* Specs */}
          {(specsEntries.length > 0 || editing) && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <h3 className="text-xs font-semibold text-zinc-400 mb-3">Especificações</h3>
              {editing ? (
                <div className="grid grid-cols-2 gap-3">
                  {Object.keys(editSpecs).map((k) => (
                    <div key={k}>
                      <label className="text-[11px] text-zinc-500 block mb-1 capitalize">{k.replace(/_/g, " ")}</label>
                      <input
                        value={editSpecs[k] ?? ""}
                        onChange={(e) => setEditSpecs((s) => ({ ...s, [k]: e.target.value }))}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500"
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                  {specsEntries.map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-zinc-500 capitalize">{k.replace(/_/g, " ")}</dt>
                      <dd className="text-zinc-200 font-medium mt-0.5">{v}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          )}

          {/* Compliance */}
          {complianceEntries.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <h3 className="text-xs font-semibold text-zinc-400 mb-3">Compliance</h3>
              {editing ? (
                <div className="flex flex-wrap gap-4">
                  {Object.keys(editCompliance).map((k) => (
                    <label key={k} className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editCompliance[k] ?? false}
                        onChange={(e) => setEditCompliance((c) => ({ ...c, [k]: e.target.checked }))}
                        className="accent-blue-500"
                      />
                      <span className="capitalize">{k.replace(/_/g, " ")}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <div className="flex flex-wrap gap-3">
                  {complianceEntries.map(([k, v]) => (
                    <span
                      key={k}
                      className={`flex items-center gap-1.5 px-2 py-1 rounded text-[11px] ${v ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}
                    >
                      {v ? "✓" : "✗"} <span className="capitalize">{k.replace(/_/g, " ")}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Edit actions */}
          {editing && (
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setEditing(false)}
                className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          )}
        </div>

        {/* Sidebar — holder + history */}
        <div className="space-y-4">
          {/* Current holder */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-zinc-400 mb-3">Titular atual</h3>
            {asset.holder_name ? (
              <div>
                <p className="text-sm font-medium text-zinc-200">{asset.holder_name}</p>
                {asset.holder_dept && (
                  <p className="text-xs text-zinc-500 mt-0.5">{asset.holder_dept}</p>
                )}
              </div>
            ) : (
              <p className="text-xs text-zinc-600">Sem titular</p>
            )}
          </div>

          {/* History */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-zinc-400 mb-3">Histórico</h3>
            {asset.history.length === 0 ? (
              <p className="text-xs text-zinc-600">Nenhum registro</p>
            ) : (
              <div className="space-y-3">
                {asset.history.map((h) => (
                  <div key={h.id} className="border-l-2 border-zinc-700 pl-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-xs font-medium text-zinc-300">
                        {ACTION_LABELS[h.action] ?? h.action}
                      </span>
                      <span className="text-[11px] text-zinc-600 shrink-0">
                        {new Date(h.changed_at).toLocaleDateString("pt-BR")}
                      </span>
                    </div>
                    {(h.holder_name || h.holder_dept) && (
                      <p className="text-[11px] text-zinc-500 mt-0.5">
                        {[h.holder_name, h.holder_dept].filter(Boolean).join(" · ")}
                      </p>
                    )}
                    {h.notes && (
                      <p className="text-[11px] text-zinc-600 mt-0.5 italic">{h.notes}</p>
                    )}
                    <p className="text-[10px] text-zinc-700 mt-0.5">por {h.changed_by}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Assign modal */}
      {showAssign && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-5 w-full max-w-sm space-y-4">
            <h3 className="text-sm font-semibold text-zinc-100">Atribuir equipamento</h3>
            {loadingUsers ? (
              <p className="text-xs text-zinc-500">Carregando usuários…</p>
            ) : (
              <div>
                <label className="text-[11px] text-zinc-500 block mb-1">Colaborador</label>
                <select
                  value={selectedUser}
                  onChange={(e) => setSelectedUser(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500"
                >
                  <option value="">Selecione…</option>
                  {users.map((u) => (
                    <option key={u.uuid} value={u.uuid}>{u.name}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="text-[11px] text-zinc-500 block mb-1">Observação (opcional)</label>
              <input
                value={assignNotes}
                onChange={(e) => setAssignNotes(e.target.value)}
                placeholder="Ex: Substituição de equipamento…"
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowAssign(false)}
                className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => void handleAssign()}
                disabled={assigning || !selectedUser}
                className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {assigning ? "Atribuindo…" : "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Return modal */}
      {showReturn && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-5 w-full max-w-sm space-y-4">
            <h3 className="text-sm font-semibold text-zinc-100">Registrar devolução</h3>
            <p className="text-xs text-zinc-500">
              Confirmar que <strong className="text-zinc-300">{asset.holder_name}</strong> devolveu o equipamento?
            </p>
            <div>
              <label className="text-[11px] text-zinc-500 block mb-1">Observação (opcional)</label>
              <input
                value={returnNotes}
                onChange={(e) => setReturnNotes(e.target.value)}
                placeholder="Motivo da devolução…"
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowReturn(false)}
                className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => void handleReturn()}
                disabled={returning}
                className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {returning ? "Registrando…" : "Confirmar devolução"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
