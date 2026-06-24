"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface Department { id: number; name: string; }

interface UserMgmt {
  uuid: string;
  name: string;
  email: string;
  login: string | null;
  jobtitle: string | null;
  department_id: number | null;
  department_name: string | null;
  superior_id: number | null;
  superior_name: string | null;
  active: boolean;
  role: string | null;
  sso_manager: boolean;
  sso_auditor: boolean;
  procure_manager: boolean;
  sso_limpeza: boolean;
  sso_guarita: boolean;
  dreadmin: boolean;
  dredepartmentadmin: boolean;
  override_role: string | null;
  created_at: string | null;
}

function UserDialog({
  open, onClose, onSave, user, departments, users,
}: {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
  user: UserMgmt | null;
  departments: Department[];
  users: UserMgmt[];
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [jobtitle, setJobtitle] = useState("");
  const [deptId, setDeptId] = useState<number | "">(""  );
  const [supUuid, setSupUuid] = useState("");
  const [ssoManager, setSsoManager] = useState(false);
  const [ssoAuditor, setSsoAuditor] = useState(false);
  const [procureManager, setProcureManager] = useState(false);
  const [ssoLimpeza, setSsoLimpeza] = useState(false);
  const [ssoGuarita, setSsoGuarita] = useState(false);
  const [dreadmin, setDreadmin] = useState(false);
  const [dredeptadmin, setDredeptadmin] = useState(false);
  const [active, setActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setName(user?.name ?? "");
    setEmail(user?.email ?? "");
    setLogin(user?.login ?? "");
    setPassword("");
    setJobtitle(user?.jobtitle ?? "");
    setDeptId(user?.department_id ?? "");
    setSsoManager(user?.sso_manager ?? false);
    setSsoAuditor(user?.sso_auditor ?? false);
    setProcureManager(user?.procure_manager ?? false);
    setSsoLimpeza(user?.sso_limpeza ?? false);
    setSsoGuarita(user?.sso_guarita ?? false);
    setDreadmin(user?.dreadmin ?? false);
    setDredeptadmin(user?.dredepartmentadmin ?? false);
    setActive(user?.active ?? true);
    // find superior uuid from users list
    const sup = users.find((u) => u.department_id === user?.superior_id || u.name === user?.superior_name);
    setSupUuid(sup?.uuid ?? "");
    setError("");
  }, [user, open, users]);

  async function handleSubmit() {
    if (!name.trim()) { setError("Nome é obrigatório"); return; }
    if (!email.trim()) { setError("Email é obrigatório"); return; }
    if (!user && !password.trim()) { setError("Senha é obrigatória para novo usuário"); return; }

    setSaving(true);
    setError("");
    try {
      const headers = { "Content-Type": "application/json" };
      const payload: Record<string, unknown> = {
        name: name.trim(),
        email: email.trim(),
        login: login.trim() || email.split("@")[0],
        jobtitle: jobtitle.trim() || null,
        department_id: deptId !== "" ? Number(deptId) : null,
        sso_manager: ssoManager,
        sso_auditor: ssoAuditor,
        procure_manager: procureManager,
        sso_limpeza: ssoLimpeza,
        sso_guarita: ssoGuarita,
        dreadmin: dreadmin,
        dredepartmentadmin: dredeptadmin,
      };
      if (password.trim()) payload.password = password.trim();
      if (!user) payload.password = password.trim();

      // find superior_id from uuid
      const supUser = users.find((u) => u.uuid === supUuid);
      payload.superior_id = supUser?.department_id ?? null; // We actually need the integer id

      const url = user ? `/api/v1/admin/user-mgmt/${user.uuid}` : "/api/v1/admin/user-mgmt";
      const method = user ? "PATCH" : "POST";
      if (user) payload.active = active;

      const res = await fetch(url, { method, headers, body: JSON.stringify(payload) });
      if (!res.ok) {
        const err = await res.json() as { detail?: string };
        setError(err.detail ?? "Erro ao salvar");
        return;
      }
      onSave();
    } finally { setSaving(false); }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 w-full max-w-lg shadow-2xl flex flex-col gap-4 max-h-[92vh] overflow-y-auto">
        <h3 className="text-sm font-semibold text-zinc-100">
          {user ? "Editar Usuário" : "Novo Usuário"}
        </h3>

        {error && <div className="px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>}

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="block text-xs text-zinc-500 mb-1">Nome *</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nome completo"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500" />
          </div>

          <div>
            <label className="block text-xs text-zinc-500 mb-1">Email *</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="usuario@empresa.com" type="email"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500" />
          </div>

          <div>
            <label className="block text-xs text-zinc-500 mb-1">Login</label>
            <input value={login} onChange={(e) => setLogin(e.target.value)} placeholder="Auto do email se vazio"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500" />
          </div>

          <div className="col-span-2">
            <label className="block text-xs text-zinc-500 mb-1">
              Senha {user ? "(deixe vazio para manter)" : "*"}
            </label>
            <input value={password} onChange={(e) => setPassword(e.target.value)} type="password"
              placeholder={user ? "••••••••" : "Mínimo 8 caracteres"}
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500" />
          </div>

          <div>
            <label className="block text-xs text-zinc-500 mb-1">Cargo</label>
            <input value={jobtitle} onChange={(e) => setJobtitle(e.target.value)} placeholder="Ex: Analista TI"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500" />
          </div>

          <div>
            <label className="block text-xs text-zinc-500 mb-1">Departamento</label>
            <select value={deptId} onChange={(e) => setDeptId(e.target.value === "" ? "" : Number(e.target.value))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500">
              <option value="">— selecione —</option>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>

          <div className="col-span-2">
            <label className="block text-xs text-zinc-500 mb-1">Superior direto</label>
            <select value={supUuid} onChange={(e) => setSupUuid(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500">
              <option value="">— nenhum —</option>
              {users.filter((u) => u.uuid !== user?.uuid).map((u) => (
                <option key={u.uuid} value={u.uuid}>{u.name}</option>
              ))}
            </select>
          </div>

          {user && (
            <div className="col-span-2 flex items-center gap-2">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-zinc-300">
                <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="accent-blue-500" />
                Usuário ativo
              </label>
            </div>
          )}

          <div className="col-span-2 space-y-2">
            <p className="text-[11px] text-zinc-500 font-medium uppercase tracking-wide">Permissões do sistema</p>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2">
              {([
                ["SSO Manager",      ssoManager,    setSsoManager],
                ["SSO Auditor",      ssoAuditor,    setSsoAuditor],
                ["Gerente Compras",  procureManager, setProcureManager],
                ["SSO Limpeza",      ssoLimpeza,    setSsoLimpeza],
                ["SSO Guarita",      ssoGuarita,    setSsoGuarita],
                ["Admin DRE",        dreadmin,      setDreadmin],
                ["Admin Depto. DRE", dredeptadmin,  setDredeptadmin],
              ] as [string, boolean, (v: boolean) => void][]).map(([label, val, setter]) => (
                <label key={label} className="flex items-center gap-2 cursor-pointer text-xs text-zinc-300">
                  <input type="checkbox" checked={val} onChange={(e) => setter(e.target.checked)} className="accent-blue-500" />
                  {label}
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-2 justify-end pt-1">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors">Cancelar</button>
          <button onClick={() => void handleSubmit()} disabled={saving}
            className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50">
            {saving ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}

const ROLE_LABEL: Record<string, string> = {
  it_admin: "Admin TI",
  it_lead: "Líder TI",
  it_agent: "Agente TI",
};

export default function AdminUsersMgmtPage() {
  const router = useRouter();
  const [users, setUsers] = useState<UserMgmt[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [filtered, setFiltered] = useState<UserMgmt[]>([]);
  const [search, setSearch] = useState("");
  const [filterActive, setFilterActive] = useState<"all" | "active" | "inactive">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  const [dialogOpen, setDialogOpen] = useState(false);
  const [selected, setSelected] = useState<UserMgmt | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<UserMgmt | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [usersRes, deptsRes] = await Promise.all([
        fetch("/api/v1/admin/user-mgmt"),
        fetch("/api/v1/admin/departments"),
      ]);
      if (usersRes.status === 401) { router.push("/login"); return; }
      if (!usersRes.ok) { setError("Erro ao carregar usuários"); return; }
      const usersData = await usersRes.json() as UserMgmt[];
      setUsers(usersData);
      applyFilters(usersData, search, filterActive);
      if (deptsRes.ok) setDepartments(await deptsRes.json() as Department[]);
    } catch { setError("Erro de rede"); }
    finally { setLoading(false); }
  }

  function applyFilters(list: UserMgmt[], q: string, status: typeof filterActive) {
    const ql = q.toLowerCase();
    let result = list;
    if (ql) result = result.filter((u) => u.name.toLowerCase().includes(ql) || u.email.toLowerCase().includes(ql));
    if (status === "active") result = result.filter((u) => u.active);
    if (status === "inactive") result = result.filter((u) => !u.active);
    setFiltered(result);
    setPage(0);
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, []);

  function handleSearch(q: string) { setSearch(q); applyFilters(users, q, filterActive); }
  function handleFilterActive(v: typeof filterActive) { setFilterActive(v); applyFilters(users, search, v); }

  async function handleToggleActive(u: UserMgmt) {
    await fetch(`/api/v1/admin/user-mgmt/${u.uuid}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: !u.active }),
    });
    await load();
  }

  async function handleDelete(u: UserMgmt) {
    setDeleting(true);
    try {
      const headers = { "Content-Type": "application/json" };
      const res = await fetch(`/api/v1/admin/user-mgmt/${u.uuid}`, { method: "DELETE", headers });
      if (!res.ok) { setError("Erro ao excluir"); return; }
      setConfirmDelete(null);
      await load();
    } finally { setDeleting(false); }
  }

  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  if (loading) return <div className="p-6 text-zinc-500 text-sm">Carregando...</div>;

  return (
    <div className="p-5 max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">Cadastro de Usuários</h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            {filtered.length} de {users.length} usuários
          </p>
        </div>
        <button onClick={() => { setSelected(null); setDialogOpen(true); }}
          className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 transition-colors">
          + Novo Usuário
        </button>
      </div>

      {error && <div className="mb-3 px-3 py-2 bg-red-500/10 text-red-400 rounded text-xs">{error}</div>}

      <div className="flex gap-2 mb-3">
        <input value={search} onChange={(e) => handleSearch(e.target.value)}
          placeholder="Buscar por nome ou email..."
          className="flex-1 bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-600" />
        <select value={filterActive} onChange={(e) => handleFilterActive(e.target.value as typeof filterActive)}
          className="bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-xs text-zinc-400 focus:outline-none">
          <option value="all">Todos</option>
          <option value="active">Ativos</option>
          <option value="inactive">Inativos</option>
        </select>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500">
              <th className="text-left px-4 py-3 font-medium">Nome</th>
              <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Email</th>
              <th className="text-left px-4 py-3 font-medium hidden lg:table-cell">Cargo</th>
              <th className="text-left px-4 py-3 font-medium hidden lg:table-cell">Departamento</th>
              <th className="text-center px-3 py-3 font-medium">Status</th>
              <th className="text-center px-3 py-3 font-medium hidden sm:table-cell">SSO</th>
              <th className="text-center px-3 py-3 font-medium hidden sm:table-cell">Papel TI</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {paged.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-zinc-600">Nenhum usuário encontrado.</td></tr>
            )}
            {paged.map((u) => (
              <tr key={u.uuid} className={`hover:bg-zinc-800/30 transition-colors ${!u.active ? "opacity-50" : ""}`}>
                <td className="px-4 py-3">
                  <div className="font-medium text-zinc-200">{u.name}</div>
                  <div className="text-zinc-500 md:hidden">{u.email}</div>
                </td>
                <td className="px-4 py-3 text-zinc-400 hidden md:table-cell">{u.email}</td>
                <td className="px-4 py-3 text-zinc-400 hidden lg:table-cell">{u.jobtitle ?? "—"}</td>
                <td className="px-4 py-3 text-zinc-400 hidden lg:table-cell">{u.department_name ?? "—"}</td>
                <td className="px-3 py-3 text-center">
                  <button onClick={() => void handleToggleActive(u)}
                    className={`px-2 py-0.5 rounded-full text-[11px] transition-colors ${
                      u.active
                        ? "bg-green-500/15 text-green-400 hover:bg-red-500/15 hover:text-red-400"
                        : "bg-zinc-700/30 text-zinc-500 hover:bg-green-500/15 hover:text-green-400"
                    }`}>
                    {u.active ? "Ativo" : "Inativo"}
                  </button>
                </td>
                <td className="px-3 py-3 text-center hidden sm:table-cell">
                  <div className="flex gap-1 justify-center">
                    {u.sso_manager && <span className="px-1 py-0.5 bg-purple-500/15 text-purple-400 rounded text-[10px]">M</span>}
                    {u.sso_auditor && <span className="px-1 py-0.5 bg-blue-500/15 text-blue-400 rounded text-[10px]">A</span>}
                    {!u.sso_manager && !u.sso_auditor && <span className="text-zinc-700">—</span>}
                  </div>
                </td>
                <td className="px-3 py-3 text-center hidden sm:table-cell">
                  {u.override_role ? (
                    <span className="px-1.5 py-0.5 bg-amber-500/15 text-amber-400 rounded text-[11px]">
                      {ROLE_LABEL[u.override_role] ?? u.override_role}
                    </span>
                  ) : <span className="text-zinc-700">—</span>}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-3 justify-end">
                    <button onClick={() => { setSelected(u); setDialogOpen(true); }}
                      className="text-blue-400 hover:text-blue-300 transition-colors">Editar</button>
                    <button onClick={() => setConfirmDelete(u)}
                      className="text-red-500 hover:text-red-400 transition-colors">Excluir</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 text-xs text-zinc-500">
          <span>Página {page + 1} de {totalPages}</span>
          <div className="flex gap-2">
            <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
              className="px-3 py-1 border border-zinc-700 rounded hover:bg-zinc-800 disabled:opacity-30 transition-colors">
              ← Anterior
            </button>
            <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page === totalPages - 1}
              className="px-3 py-1 border border-zinc-700 rounded hover:bg-zinc-800 disabled:opacity-30 transition-colors">
              Próxima →
            </button>
          </div>
        </div>
      )}

      <UserDialog
        open={dialogOpen}
        onClose={() => { setDialogOpen(false); setSelected(null); }}
        onSave={() => { setDialogOpen(false); setSelected(null); void load(); }}
        user={selected}
        departments={departments}
        users={users}
      />

      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 w-full max-w-sm shadow-2xl">
            <h3 className="text-sm font-semibold text-zinc-100 mb-2">Excluir usuário</h3>
            <p className="text-xs text-zinc-400 mb-1">
              Tem certeza que deseja excluir <span className="font-medium text-zinc-200">{confirmDelete.name}</span>?
            </p>
            <p className="text-xs text-red-400 mb-5">Esta ação é irreversível e remove o acesso a todos os sistemas.</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmDelete(null)} className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors">Cancelar</button>
              <button onClick={() => void handleDelete(confirmDelete)} disabled={deleting}
                className="px-3 py-1.5 bg-red-600 text-white text-xs rounded-md hover:bg-red-700 transition-colors disabled:opacity-50">
                {deleting ? "Excluindo..." : "Excluir"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
