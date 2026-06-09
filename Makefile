.PHONY: dev test migrate lint build down frontend-bootstrap

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

# Apply Alembic migrations via the running backend container
migrate:
	docker exec helpdesk-backend alembic upgrade head

# Lint backend
lint:
	cd backend && ruff check app/ tests/ && ruff format --check app/ tests/

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
