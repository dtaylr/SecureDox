# Local Runtime

Phase 2 runs a small document-intake stack: web, API, worker, Postgres, Redis,
shared local document storage, and an nginx gateway.

## Start

```bash
make bootstrap
make up
```

The API container runs migrations and seed data on startup. Re-run seed data
manually when needed:

```bash
make seed
```

## URLs

- Web app: http://localhost:3000
- API health: http://localhost:8000/health
- API readiness: http://localhost:8000/ready
- API docs: http://localhost:8000/docs
- Gateway: http://localhost:8080

## Demo Login

All demo users use the password `securedox-demo`.

- `admin`
- `reviewer`
- `uploader`

The default tenant is `acme-lending`. Seed data also creates
`northwind-health`.

## Stop

```bash
make down
```

## Phase 3 Smoke Tests

With the stack running:

```bash
make test-api
make test-db
make test-security
yarn test:e2e
```

Or run the critical smoke lane:

```bash
make test-smoke
```
