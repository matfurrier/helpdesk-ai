# Learnings

[L-01] 2026-07-14 — Presigned URL do MinIO não serve para o browser: a assinatura AWS4 inclui o header `host`, então a URL só é válida no hostname usado para assiná-la (`minio:9000`, interno da rede Docker). O download de anexos agora é servido pelo próprio backend (`storage.get` + `Response`), que já autentica e autoriza; evita expor o MinIO publicamente e assinar com hostname externo. Uploads são limitados a 10 MB, então ler o objeto inteiro em memória é aceitável.

[L-02] 2026-07-14 — Para exercitar código do backend contra o DB e o MinIO reais sem tocar no serviço do Swarm: `docker run --rm --network container:$(docker ps -qf name=helpdesk_backend.1)` reaproveita o namespace de rede do container vivo (resolve `minio` **e** `tasks.infra_postgres`, que estão em redes diferentes) com o source bind-mountado read-only. Precisa de `--user 0:0` — o usuário não-root da imagem não lê os arquivos montados do host.
