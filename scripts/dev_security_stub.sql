-- CI/test stub for the shared user directory (public.users in the security database).
-- Replicates the minimum columns used by helpdesk-ai auth against the real database.
-- Run on the LOCAL test postgres only. Never run on the shared security database.

-- The real database has tables in the 'public' schema; match that here.

CREATE TABLE IF NOT EXISTS public.users (
  id            serial PRIMARY KEY,
  uuid          uuid UNIQUE,         -- native uuid, matches real schema (asyncpg returns UUID obj)
  login         text,
  name          text NOT NULL DEFAULT '',
  email         text,
  password      text,                -- argon2id hash
  active        smallint NOT NULL DEFAULT 1,  -- matches real schema (not boolean)
  departmentid  integer
);

CREATE TABLE IF NOT EXISTS public.department (
  id    serial PRIMARY KEY,
  name  varchar(255) NOT NULL
);

-- Seed TI department (id=1) so departmentid=1 → it_agent works in tests
INSERT INTO public.department (id, name) VALUES (1, 'TI') ON CONFLICT DO NOTHING;
