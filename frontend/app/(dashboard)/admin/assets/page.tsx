"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface AssetListItem {
  id: string;
  asset_tag: string | null;
  asset_type: string;
  brand: string | null;
  model: string;
  status: string;
  holder_name: string | null;
  holder_dept: string | null;
  acquired_at: string | null;
  updated_at: string;
}

interface AssetListOut {
  items: AssetListItem[];
  total: number;
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

async function getCsrfHeaders(): Promise<HeadersInit> {
  await fetch("/api/v1/auth/csrf-token");
  const csrf =
    document.cookie.split("; ").find((c) => c.startsWith("csrf_token="))?.split("=")[1] ?? "";
  return { "Content-Type": "application/json", "X-CSRF-Token": csrf };
}

interface NewAssetForm {
  asset_tag: string;
  asset_type: string;
  brand: string;
  model: string;
  serial_number: string;
  status: string;
  acquired_at: string;
  notes: string;
  // notebook specs
  computer_name: string;
  os_version: string;
  processor: string;
  ram: string;
  storage: string;
  // compliance
  antivirus: boolean;
  fusion_inventory: boolean;
  responsibility_term: boolean;
  // smartphone specs
  phone_number: string;
}

const EMPTY_FORM: NewAssetForm = {
  asset_tag: "",
  asset_type: "notebook",
  brand: "",
  model: "",
  serial_number: "",
  status: "active",
  acquired_at: "",
  notes: "",
  computer_name: "",
  os_version: "",
  processor: "",
  ram: "",
  storage: "",
  antivirus: false,
  fusion_inventory: false,
  responsibility_term: false,
  phone_number: "",
};

export default function AdminAssetsPage() {
  const router = useRouter();
  const [items, setItems] = useState<AssetListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<NewAssetForm>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (typeFilter) params.set("asset_type", typeFilter);
      if (statusFilter) params.set("status", statusFilter);
      if (search) params.set("search", search);
      const res = await fetch(`/api/v1/admin/assets?${params.toString()}`);
      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) { setError("Erro ao carregar patrimônio"); return; }
      const data = (await res.json()) as AssetListOut;
      setItems(data.items);
      setTotal(data.total);
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, [typeFilter, statusFilter]);

  function handleSearchKey(e: React.KeyboardEvent) {
    if (e.key === "Enter") void load();
  }

  function buildSpecs(): Record<string, string> {
    if (form.asset_type === "notebook") {
      return {
        computer_name: form.computer_name,
        os_version: form.os_version,
        processor: form.processor,
        ram: form.ram,
        storage: form.storage,
      };
    }
    if (form.asset_type === "smartphone") {
      return { phone_number: form.phone_number };
    }
    return {};
  }

  function buildCompliance(): Record<string, boolean> {
    if (form.asset_type === "notebook") {
      return {
        antivirus: form.antivirus,
        fusion_inventory: form.fusion_inventory,
        responsibility_term: form.responsibility_term,
      };
    }
    return {};
  }

  async function handleCreate() {
    if (!form.model.trim()) return;
    setCreating(true);
    setError("");
    try {
      const headers = await getCsrfHeaders();
      const body = {
        asset_tag: form.asset_tag || null,
        asset_type: form.asset_type,
        brand: form.brand || null,
        model: form.model,
        serial_number: form.serial_number || null,
        status: form.status,
        acquired_at: form.acquired_at || null,
        notes: form.notes || null,
        specs: buildSpecs(),
        compliance: buildCompliance(),
      };
      const res = await fetch("/api/v1/admin/assets", {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = (await res.json()) as { detail?: string };
        setError(err.detail ?? "Erro ao criar patrimônio");
        return;
      }
      setForm(EMPTY_FORM);
      setShowForm(false);
      await load();
    } finally { setCreating(false); }
  }

  function handleExport() {
    const params = new URLSearchParams();
    if (typeFilter) params.set("asset_type", typeFilter);
    if (statusFilter) params.set("status", statusFilter);
    window.location.href = `/api/v1/admin/assets/export?${params.toString()}`;
  }

  const setField = (k: keyof NewAssetForm, v: string | boolean) =>
    setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="p-5 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">Patrimônio de TI</h2>
          <p className="text-xs text-zinc-500 mt-0.5">{total} equipamentos cadastrados</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleExport}
            className="px-3 py-1.5 bg-zinc-800 text-zinc-300 text-xs rounded-md hover:bg-zinc-700 transition-colors border border-zinc-700"
          >
            Exportar CSV
          </button>
          <button
            onClick={() => { setShowForm(!showForm); setError(""); }}
            className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors"
          >
            + Novo Equipamento
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>
      )}

      {/* Create form */}
      {showForm && (
        <div className="mb-4 bg-zinc-900 border border-zinc-700 rounded-lg p-4 space-y-3">
          <h3 className="text-xs font-semibold text-zinc-300">Novo Equipamento</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div>
              <label className="text-[11px] text-zinc-500 block mb-1">Tipo *</label>
              <select
                value={form.asset_type}
                onChange={(e) => setField("asset_type", e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500"
              >
                {Object.entries(TYPE_LABELS).map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] text-zinc-500 block mb-1">Marca</label>
              <input
                value={form.brand}
                onChange={(e) => setField("brand", e.target.value)}
                placeholder="Dell, Samsung…"
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-500 block mb-1">Modelo *</label>
              <input
                value={form.model}
                onChange={(e) => setField("model", e.target.value)}
                placeholder="Inspiron 15 3511"
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-500 block mb-1">Patrimônio / Placa</label>
              <input
                value={form.asset_tag}
                onChange={(e) => setField("asset_tag", e.target.value)}
                placeholder="002.523"
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-500 block mb-1">Serial</label>
              <input
                value={form.serial_number}
                onChange={(e) => setField("serial_number", e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div>
              <label className="text-[11px] text-zinc-500 block mb-1">Status</label>
              <select
                value={form.status}
                onChange={(e) => setField("status", e.target.value)}
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
                value={form.acquired_at}
                onChange={(e) => setField("acquired_at", e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500"
              />
            </div>
          </div>

          {/* Notebook-specific specs */}
          {form.asset_type === "notebook" && (
            <>
              <div className="border-t border-zinc-800 pt-3">
                <p className="text-[11px] font-medium text-zinc-400 mb-2">Especificações</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {([
                    ["computer_name", "Nome do computador (ex: DSFIS009)"],
                    ["os_version", "Sistema Operacional"],
                    ["processor", "Processador"],
                    ["ram", "Memória RAM"],
                    ["storage", "Armazenamento"],
                  ] as [keyof NewAssetForm, string][]).map(([k, ph]) => (
                    <div key={k}>
                      <label className="text-[11px] text-zinc-500 block mb-1 capitalize">{k.replace("_", " ")}</label>
                      <input
                        value={form[k] as string}
                        onChange={(e) => setField(k, e.target.value)}
                        placeholder={ph}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
                      />
                    </div>
                  ))}
                </div>
              </div>
              <div className="border-t border-zinc-800 pt-3">
                <p className="text-[11px] font-medium text-zinc-400 mb-2">Compliance</p>
                <div className="flex gap-6">
                  {([
                    ["antivirus", "Antivírus"],
                    ["fusion_inventory", "Fusion Inventory"],
                    ["responsibility_term", "Termo de Responsabilidade"],
                  ] as [keyof NewAssetForm, string][]).map(([k, label]) => (
                    <label key={k} className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form[k] as boolean}
                        onChange={(e) => setField(k, e.target.checked)}
                        className="accent-blue-500"
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Smartphone-specific */}
          {form.asset_type === "smartphone" && (
            <div className="border-t border-zinc-800 pt-3">
              <p className="text-[11px] font-medium text-zinc-400 mb-2">Dados do aparelho</p>
              <div className="max-w-xs">
                <label className="text-[11px] text-zinc-500 block mb-1">Número de telefone</label>
                <input
                  value={form.phone_number}
                  onChange={(e) => setField("phone_number", e.target.value)}
                  placeholder="(43) 99123-4567"
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
                />
              </div>
            </div>
          )}

          <div>
            <label className="text-[11px] text-zinc-500 block mb-1">Observações</label>
            <input
              value={form.notes}
              onChange={(e) => setField("notes", e.target.value)}
              placeholder="Tela quebrada, em garantia…"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            />
          </div>

          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}
              className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={() => void handleCreate()}
              disabled={creating || !form.model.trim()}
              className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {creating ? "Cadastrando..." : "Cadastrar"}
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-3 flex-wrap">
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-zinc-600"
        >
          <option value="">Todos os tipos</option>
          {Object.entries(TYPE_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-zinc-600"
        >
          <option value="">Todos os status</option>
          {Object.entries(STATUS_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={handleSearchKey}
          placeholder="Buscar modelo, patrimônio, titular… (Enter)"
          className="flex-1 min-w-[220px] bg-zinc-900 border border-zinc-800 rounded px-3 py-1.5 text-xs text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-zinc-600"
        />
        <button
          onClick={() => void load()}
          className="px-3 py-1.5 bg-zinc-800 text-zinc-300 text-xs rounded hover:bg-zinc-700 transition-colors"
        >
          Buscar
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-zinc-500 text-sm py-6">Carregando...</div>
      ) : items.length === 0 ? (
        <div className="text-zinc-600 text-sm py-8 text-center">Nenhum equipamento encontrado.</div>
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500">
                <th className="text-left px-4 py-3 font-medium">Patrimônio</th>
                <th className="text-left px-4 py-3 font-medium">Tipo / Modelo</th>
                <th className="text-left px-4 py-3 font-medium">Titular</th>
                <th className="text-left px-4 py-3 font-medium">Setor</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Aquisição</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="px-4 py-3 font-mono text-zinc-400">
                    {item.asset_tag ?? <span className="text-zinc-700">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-zinc-200 font-medium truncate max-w-[200px]">
                      {item.brand ? `${item.brand} ${item.model}` : item.model}
                    </div>
                    <div className="text-zinc-600 mt-0.5">{TYPE_LABELS[item.asset_type] ?? item.asset_type}</div>
                  </td>
                  <td className="px-4 py-3 text-zinc-300">
                    {item.holder_name ?? <span className="text-zinc-700">Sem titular</span>}
                  </td>
                  <td className="px-4 py-3 text-zinc-500">{item.holder_dept ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-[11px] ${STATUS_COLORS[item.status] ?? "text-zinc-400"}`}>
                      {STATUS_LABELS[item.status] ?? item.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-500">
                    {item.acquired_at ? item.acquired_at.slice(0, 10) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/assets/${item.id}`}
                      className="text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      Ver
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
