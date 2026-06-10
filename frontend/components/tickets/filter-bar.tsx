"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback } from "react";

interface FilterDept {
  id: number;
  name: string;
}

interface FilterUser {
  id: string;
  name: string;
}

interface FilterCategory {
  id: string;
  slug: string;
  name: string;
}

interface FilterOptionsOut {
  years: number[];
  departments: FilterDept[];
  users: FilterUser[];
  categories?: FilterCategory[];
}

interface Props {
  options: FilterOptionsOut;
}

const MONTHS = [
  { value: 1, label: "Janeiro" },
  { value: 2, label: "Fevereiro" },
  { value: 3, label: "Março" },
  { value: 4, label: "Abril" },
  { value: 5, label: "Maio" },
  { value: 6, label: "Junho" },
  { value: 7, label: "Julho" },
  { value: 8, label: "Agosto" },
  { value: 9, label: "Setembro" },
  { value: 10, label: "Outubro" },
  { value: 11, label: "Novembro" },
  { value: 12, label: "Dezembro" },
];

export function FilterBar({ options }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const year = searchParams.get("year") ?? "";
  const month = searchParams.get("month") ?? "";
  const deptId = searchParams.get("dept_id") ?? "";
  const userId = searchParams.get("user_id") ?? "";
  const categorySlug = searchParams.get("category_slug") ?? "";

  const update = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) params.set(key, value);
      else params.delete(key);
      router.push(`${pathname}?${params.toString()}`);
    },
    [router, pathname, searchParams],
  );

  const clear = useCallback(() => {
    router.push(pathname);
  }, [router, pathname]);

  const hasFilters = year || month || deptId || userId || categorySlug;

  const selectCls =
    "bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500/50 min-w-[120px]";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={year}
        onChange={(e) => update("year", e.target.value)}
        className={selectCls}
      >
        <option value="">Todos os anos</option>
        {options.years.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>

      <select
        value={month}
        onChange={(e) => update("month", e.target.value)}
        className={selectCls}
      >
        <option value="">Todos os meses</option>
        {MONTHS.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </select>

      <select
        value={deptId}
        onChange={(e) => update("dept_id", e.target.value)}
        className={selectCls}
      >
        <option value="">Todos os depto.</option>
        {options.departments.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>

      <select
        value={userId}
        onChange={(e) => update("user_id", e.target.value)}
        className={selectCls}
      >
        <option value="">Todos os usuários</option>
        {options.users.map((u) => (
          <option key={u.id} value={u.id}>
            {u.name}
          </option>
        ))}
      </select>

      {(options.categories ?? []).length > 0 && (
        <select
          value={categorySlug}
          onChange={(e) => update("category_slug", e.target.value)}
          className={selectCls}
        >
          <option value="">Todas as categorias</option>
          {(options.categories ?? []).map((c) => (
            <option key={c.slug} value={c.slug}>
              {c.name}
            </option>
          ))}
        </select>
      )}

      {hasFilters && (
        <button
          onClick={clear}
          className="text-xs text-zinc-500 hover:text-zinc-300 px-2 py-1.5 transition-colors"
        >
          × Limpar
        </button>
      )}
    </div>
  );
}
