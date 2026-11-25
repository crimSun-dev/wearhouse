-- Wearhouse v2 database/role provisioning (run once per environment by a DBA/superuser).
-- One dedicated database per environment; never reuse the legacy demo database or credentials.
--   psql -v env=dev -v runtime_pw="'...'" -v migrator_pw="'...'" -f provision_roles.sql
CREATE ROLE wearhouse_migrator LOGIN PASSWORD :migrator_pw;          -- owns schema objects, runs migrations
CREATE ROLE wearhouse_runtime  LOGIN PASSWORD :runtime_pw NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE wearhouse_:env OWNER wearhouse_migrator;
\connect wearhouse_:env
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE wearhouse_:env FROM PUBLIC;
GRANT CONNECT ON DATABASE wearhouse_:env TO wearhouse_runtime;
GRANT USAGE ON SCHEMA public TO wearhouse_runtime;
-- Table privileges are granted by the migrations themselves:
--   wearhouse migrate --environment <env> --runtime-role wearhouse_runtime
-- The API refuses to start if its role can CREATE in the database/schema or is a superuser
-- (outside WEARHOUSE_ENV=development), or lacks any required table privilege.
