"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";

// Relative URL — Next.js rewrites /api/v1/* to the backend container
const API = "";

interface CsatStatus {
  ticket_id: string;
  ticket_number: string;
  title: string;
  status: string;
  already_responded: boolean;
  rating: number | null;
}

function StarRating({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: number) => void;
}) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-2">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          onMouseEnter={() => setHover(star)}
          onMouseLeave={() => setHover(0)}
          className="text-4xl transition-transform hover:scale-110 focus:outline-none"
          aria-label={`${star} estrela${star > 1 ? "s" : ""}`}
        >
          <span className={star <= (hover || value) ? "text-yellow-400" : "text-zinc-600"}>
            ★
          </span>
        </button>
      ))}
    </div>
  );
}

const LABELS: Record<number, string> = {
  1: "Muito insatisfeito",
  2: "Insatisfeito",
  3: "Neutro",
  4: "Satisfeito",
  5: "Muito satisfeito",
};

export default function CsatPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";

  const [info, setInfo] = useState<CsatStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/v1/public/csat/${token}`)
      .then(async (r) => {
        if (!r.ok) throw new Error("Link inválido ou expirado.");
        return r.json() as Promise<CsatStatus>;
      })
      .then((d) => {
        setInfo(d);
        if (d.already_responded && d.rating) setRating(d.rating);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Erro ao carregar pesquisa.")
      )
      .finally(() => setLoading(false));
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!rating) return;
    setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/v1/public/csat/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, comment: comment || null }),
      });
      if (!r.ok) {
        const data = (await r.json()) as { detail?: string };
        throw new Error(data.detail ?? "Erro ao enviar avaliação.");
      }
      setDone(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao enviar.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-2xl p-8 shadow-xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="text-2xl font-bold text-white mb-1">IT Helpdesk</div>
          <div className="text-zinc-400 text-sm">Pesquisa de satisfação</div>
        </div>

        {loading && (
          <div className="text-center text-zinc-400 py-8">Carregando...</div>
        )}

        {!loading && error && (
          <div className="text-center">
            <div className="text-red-400 mb-4">{error}</div>
            <p className="text-zinc-500 text-sm">
              Se acredita que houve um erro, entre em contato com a TI.
            </p>
          </div>
        )}

        {!loading && info && !error && (
          <>
            {/* Ticket info */}
            <div className="mb-6 p-4 bg-zinc-800 rounded-xl">
              <div className="text-xs text-zinc-400 mb-1">{info.ticket_number}</div>
              <div className="text-white font-medium text-sm leading-snug">
                {info.title}
              </div>
            </div>

            {info.already_responded || done ? (
              <div className="text-center py-4">
                <div className="text-3xl mb-3">🙏</div>
                <p className="text-white font-semibold text-lg mb-2">
                  Obrigado pela sua avaliação!
                </p>
                <p className="text-zinc-400 text-sm">
                  Sua opinião nos ajuda a melhorar continuamente.
                </p>
                {(info.rating || rating) > 0 && (
                  <div className="mt-4 flex justify-center gap-1">
                    {[1, 2, 3, 4, 5].map((s) => (
                      <span
                        key={s}
                        className={`text-2xl ${s <= (info.rating ?? rating) ? "text-yellow-400" : "text-zinc-700"}`}
                      >
                        ★
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-6">
                <div>
                  <label className="block text-zinc-300 text-sm font-medium mb-3">
                    Como você avalia o atendimento?
                  </label>
                  <div className="flex flex-col items-center gap-2">
                    <StarRating value={rating} onChange={setRating} />
                    {rating > 0 && (
                      <span className="text-zinc-400 text-sm">{LABELS[rating]}</span>
                    )}
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="comment"
                    className="block text-zinc-300 text-sm font-medium mb-2"
                  >
                    Comentário <span className="text-zinc-500">(opcional)</span>
                  </label>
                  <textarea
                    id="comment"
                    rows={3}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    maxLength={1000}
                    placeholder="Como podemos melhorar?"
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2
                               text-zinc-200 text-sm placeholder-zinc-600 focus:outline-none
                               focus:ring-1 focus:ring-blue-500/50 resize-none"
                  />
                </div>

                {error && (
                  <div className="text-red-400 text-sm text-center">{error}</div>
                )}

                <button
                  type="submit"
                  disabled={!rating || submitting}
                  className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40
                             disabled:cursor-not-allowed text-white font-semibold rounded-xl
                             transition-colors"
                >
                  {submitting ? "Enviando..." : "Enviar avaliação"}
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </div>
  );
}
