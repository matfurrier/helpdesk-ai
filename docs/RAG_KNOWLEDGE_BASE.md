# RAG_KNOWLEDGE_BASE.md — base de conhecimento e recuperação

## 1. Objetivo

A IA de triagem precisa responder com **fatos da empresa**, não com conhecimento genérico. O RAG provê esse contexto em tempo real, com citações e isolamento por nível de confiança.

## 2. Fontes suportadas

| `source_type`        | Origem                                                      | Exemplos                                  | Default trust       |
|----------------------|-------------------------------------------------------------|-------------------------------------------|---------------------|
| `internal_kb`        | Artigos criados/aprovados no próprio helpdesk-ai            | "Como acessar VPN", "Reset de SAP B1"     | `internal_published`|
| `manual_pdf`         | PDFs colocados em diretório monitorado (`/var/kb/pdfs/`)    | Manuais de impressora, contratos          | `external_doc`      |
| `internal_docs`      | Google Drive / SharePoint (via conector futuro)             | Procedimentos do TI                       | `internal_only`     |
| `repo_md`            | Repositórios de runbook (git clone agendado)                | `ops-runbooks/*.md`                       | `internal_only`     |
| `runbook`            | Texto livre colado pelo admin                               | "Procedimento incidente Cisco Umbrella"   | `internal_only`     |
| `legacy_kb`          | Export da KB do GLPI                                        | Importação one-shot                       | `internal_published`|
| `external_doc`       | Documentação pública aprovada (Microsoft, SAP, fornecedor)  | Doc oficial Outlook                       | `external_doc`      |

Cada fonte é uma linha em `helpdesk_rag.sources`. Sources com `enabled=false` não rodam mais ingestão; seus chunks continuam pesquisáveis até admin invalidar.

## 3. Pipeline de ingestão

```
Discover → Fetch → Extract → Sanitize → Chunk → Hash → Embed → Persist → Index → Log
```

### 3.1. Discover
Worker agendado (`workers/rag_ingest.py`) percorre cada `source.enabled=true` segundo seu `schedule_cron`. Cada execução cria linha em `helpdesk_rag.ingestion_runs` (status: `running`/`succeeded`/`failed`).

### 3.2. Fetch
Conector específico por `source_type`. Timeout 30s. Erros vão para `ingestion_runs.error_log` (jsonb).

### 3.3. Extract
- PDF: `pypdf` para texto, `pdfplumber` para tabelas, `pytesseract` se `is_scanned=true` (detectado por densidade de texto < limiar).
- DOCX: `python-docx`.
- Markdown: parse direto, preserva headings como metadados (`section_path`).
- HTML: `selectolax` + remoção de nav/aside/script/style.

### 3.4. Sanitize
- Normalização NFKC.
- Remoção de bytes nulos e control chars.
- **Detecção de instruções embutidas** (mesmo regex do redactor de input): se um chunk contém `ignore previous`, `SYSTEM:`, `</system>`, etc., ele é marcado `suspicious=true` e fica fora do retrieval para colaboradores comuns. Admin é notificado.
- Truncamento: chunks individuais ≤ 1200 tokens (depois de chunking).

### 3.5. Chunk
- Estratégia: **sliding window** com 800 tokens e 100 de overlap.
- Quebra preferencial em parágrafo > sentença > token.
- Metadados por chunk: `source_id`, `document_id`, `section_path`, `position`, `trust_level` (herdado do source, podendo ser sobrescrito).

### 3.6. Hash & dedup
- `chunk_hash = sha256(normalized_text)`.
- Se hash já existe na mesma `source_id`, pula embedding (economia de custo).

### 3.7. Embed
- Modelo: `text-embedding-3-small` (1536 dims). Trocável via `helpdesk.ai_settings`.
- Batch de até 100 chunks por chamada.
- Falha do provider: retry com backoff exponencial (3 tentativas, jitter). Após falha definitiva → chunk permanece com `embedding IS NULL`, fica fora do retrieval.

### 3.8. Persist & index
- Tabela `helpdesk_rag.chunks` com coluna `embedding vector(1536)`.
- Índice **HNSW** com `vector_cosine_ops`, `m=16`, `ef_construction=64`.
- Reindex agendado mensalmente (worker).

### 3.9. Log
- Cada run grava: total fetched, extracted, chunked, embedded, dedup_skipped, suspicious_flagged, duration_ms.
- Telemetria visível no painel admin.

## 4. Retrieval (síncrono, durante o chat)

```
[mensagem do usuário]
   ↓
[opcional] Query rewrite (LLM cheap, ≤ 200 tokens output)
   ↓  → 3 variações da query (semântica próxima, palavras-chave, reformulação)
[embed (1 chamada com batch de 3 queries)]
   ↓
[top-K retrieval no pgvector (k=8) com filtro por trust_level + role do usuário]
   ↓
[Rerank LLM cheap → top-3]
   ↓
[Injeta em <context> do prompt principal]
```

### 4.1. Quando rodar query rewrite
- Se `len(message.split()) < 6` OU se conversa tem só 1 turn.
- Caso contrário, usa a mensagem original como query única (economiza chamada).

### 4.2. Filtros obrigatórios na busca SQL
```sql
WHERE c.embedding IS NOT NULL
  AND c.suspicious = false
  AND c.trust_level = ANY(:allowed_levels)   -- depende do role do usuário
  AND s.enabled = true
ORDER BY c.embedding <=> :query_embedding
LIMIT :k;
```

Mapeamento role → trust_levels permitidos:
- `employee`: `['internal_published', 'external_doc']`
- `it_agent`, `it_lead`, `it_admin`: `['internal_published', 'internal_only', 'external_doc']`
- `internal_draft` nunca aparece em retrieval (só preview no admin).

### 4.3. Threshold
- Score (distância cosine) ≥ 0.68 (= similaridade ≤ 0.32) → descarta.
- Se top-3 final tem score < threshold → IA recebe `<context/>` vazio e responde de acordo com regra "não sei, posso abrir ticket".

### 4.4. Citação obrigatória
- Toda sugestão da IA referencia chunks via `[#chunk_id]`.
- Frontend resolve `#chunk_id` → título do documento + deep link interno (`/kb/{article_slug}#chunk-{n}`).
- Se IA cita ID inexistente → validação rejeita, retry com aviso.

## 5. Gaps (lacunas da base)

Quando um chat termina sem auto-resolução e a IA não achou contexto relevante (score < threshold ou `<context/>` vazio), uma linha vai para `helpdesk_rag.gaps`:

```
gap_id, conversation_id, ticket_id, original_query, top_score, suggested_topic, created_at
```

Admin vê painel "Gaps" priorizado por frequência. Pode criar artigo KB direto a partir do ticket resolvido (worker reusa o transcript + resolução do analista como prompt para `KB_ARTICLE_DRAFT_SYSTEM`).

## 6. Atualização de embeddings após mudança de modelo

Se admin trocar `OPENAI_EMBED_MODEL` em `ai_settings`:
1. Sistema cria novo `embedding_set_id` (versão dos vetores).
2. Worker reembeda todos os chunks em background.
3. Retrieval usa só vetores do `embedding_set_id` ativo.
4. Vetores antigos podem ser purgados após validação.

## 7. Métricas e observabilidade

Dashboard admin mostra:
- Cobertura: % de chats que tiveram pelo menos 1 chunk acima do threshold.
- Taxa de auto-resolução por categoria.
- Top 20 gaps (queries sem resposta).
- Top KB articles citados.
- Latência média do retrieval (alvo: p95 < 250ms).
- Custo estimado de embeddings/mês.

## 8. Limitações conhecidas (V1)

- Sem reranker dedicado (modelo de IA cheap faz reranking ad-hoc).
- Sem cross-encoder semântico.
- Sem multi-modal (imagens em PDFs viram texto via OCR, sem análise visual).
- Conector Google Drive/SharePoint fica para fase 2.
- Sem versionamento granular de chunks (snapshot é por document).
