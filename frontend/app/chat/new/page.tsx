export default function NewChatPage() {
  return (
    <main className="min-h-screen bg-muted/20 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-xl font-semibold">Chat de triagem</h1>
        <p className="text-sm text-muted-foreground mt-2">
          Disponível no Sprint 1 — implementação do orquestrador de IA.
        </p>
        <a href="/dashboard" className="text-sm text-primary underline mt-4 block">
          ← Voltar ao dashboard
        </a>
      </div>
    </main>
  );
}
