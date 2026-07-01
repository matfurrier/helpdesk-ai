.PHONY: dev test migrate migrate-swarm migrate-prod deploy-swarm lint ci-local build down frontend-bootstrap

# Start all services with hot-reload
dev:
	docker compose up --build

# Run backend unit tests (no DB needed)
test:
	docker exec helpdesk-backend python3 -m pytest tests/unit/ -v

# Run integration tests (requires running postgres)
test-int:
	docker exec helpdesk-backend python3 -m pytest -m integration -v

# Run prompt injection suite
test-pi:
	docker exec helpdesk-backend python3 -m pytest -m prompt_injection -v

# Apply Alembic migrations via the running backend container (dev/local only)
migrate:
	docker exec helpdesk-backend alembic upgrade head

# Build prod images and deploy to Swarm, sourcing .env first so all vars expand correctly.
# --force-recreate ensures local-tagged images (no registry digest) are always restarted.
# Usage: make deploy-swarm
deploy-swarm:
	docker build -t helpdesk-backend:prod ./backend
	docker build -t helpdesk-frontend:prod ./frontend
	set -a && . ./.env && set +a && docker stack deploy -c docker-compose.swarm.yml helpdesk
	docker service update --force helpdesk_backend
	docker service update --force helpdesk_frontend

# Run migration inside any running Swarm backend replica.
# The container already has DATABASE_URL pointing to infra_postgres.
# Usage: make migrate-swarm
migrate-swarm:
	@CONTAINER=$$(docker ps -qf name=helpdesk_backend | head -1); \
	[ -z "$$CONTAINER" ] && echo "ERROR: no running helpdesk_backend container found" && exit 1; \
	docker exec $$CONTAINER alembic upgrade head

# Run migration as an ephemeral container against prod DB.
# Requires IMAGE and DATABASE_URL exported in the calling shell (not passed as
# a make var) so the credential never appears in `ps`/shell history via argv.
# Usage: set -a && . ./.env && set +a
#        export DATABASE_URL="postgresql+asyncpg://${INFRA_POSTGRES_USER}:${INFRA_POSTGRES_PASSWORD}@${INFRA_POSTGRES_HOST}:5432/${INFRA_POSTGRES_DB}"
#        IMAGE=helpdesk-backend:prod make migrate-prod
migrate-prod:
	docker run --rm \
	  --network data \
	  -e DATABASE_URL \
	  -e SECURITY_DB_HOST \
	  -e SECURITY_DB_PORT \
	  -e SECURITY_DB_USER \
	  -e SECURITY_DB_PASSWORD \
	  -e SECURITY_DB_NAME \
	  -e SECRET_KEY \
	  $(IMAGE) \
	  alembic upgrade head

# Lint backend
lint:
	cd backend && ruff check app/ tests/ && ruff format --check app/ tests/

# Run the exact same checklist as CI — run before every push
# Requires: docker compose up (backend), pnpm installed in frontend
ci-local:
	docker exec helpdesk-backend python3 -m ruff check app/ tests/
	docker exec helpdesk-backend python3 -m ruff format --check app/ tests/
	@echo "lint+format clean"
	docker exec helpdesk-backend python3 -m mypy --config-file pyproject.toml app/services app/core
	docker exec helpdesk-backend python3 -m pytest -q
	cd frontend && pnpm lint
	cd frontend && pnpm typecheck
	cd frontend && pnpm test

# Stop all containers
down:
	docker compose down

# Stop and remove volumes (destructive!)
down-v:
	docker compose down -v

# Bootstrap frontend: install deps + ShadCN init + core components (idempotent)
frontend-bootstrap:
	cd frontend && pnpm install && \
	pnpm dlx shadcn@latest init --yes && \
	pnpm dlx shadcn@latest add button input card dialog toast --yes

# Open psql shell to local helpdesk DB
psql:
	docker exec -it helpdesk-postgres psql -U $(shell grep ^POSTGRES_USER .env | cut -d= -f2) $(shell grep ^POSTGRES_DB .env | cut -d= -f2)
