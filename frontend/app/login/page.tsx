"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const schema = z.object({
  credential: z.string().min(1, "Informe o e-mail ou login"),
  password: z.string().min(1, "Informe a senha"),
});

type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(data: FormData) {
    setLoading(true);
    setError(null);
    try {
      const { csrf_token } = await api.get<{ csrf_token: string }>("/api/v1/auth/csrf-token");

      await api.post("/api/v1/auth/login", data, {
        headers: { "X-CSRF-Token": csrf_token },
      });
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao autenticar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40 px-4">
      <div className="w-full max-w-sm rounded-xl border bg-card shadow-sm p-8">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">IT Helpdesk</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Entre com seu login corporativo
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} method="post" className="space-y-4">
          <div>
            <label className="text-sm font-medium" htmlFor="credential">
              E-mail ou login
            </label>
            <input
              id="credential"
              type="text"
              autoComplete="username"
              className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              {...register("credential")}
            />
            {errors.credential && (
              <p className="text-xs text-destructive mt-1">{errors.credential.message}</p>
            )}
          </div>

          <div>
            <label className="text-sm font-medium" htmlFor="password">
              Senha
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-xs text-destructive mt-1">{errors.password.message}</p>
            )}
          </div>

          {error && (
            <p className="text-sm text-destructive bg-destructive/10 rounded-md px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {loading ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
