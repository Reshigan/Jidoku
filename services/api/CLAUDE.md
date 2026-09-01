# CLAUDE.md — services/api
FastAPI over jidoka-core. Routers stay thin: NO business logic here — gates live in jidoka-core so they cannot be
bypassed by a different client. Error mapping: gate violations -> 403, blocked plans -> 409, invalid IR -> 422.
E2 adds OIDC + roles: builder/reviewer/approver/auditor; SoD must then be enforced from the authenticated identity,
not the request body. Every endpoint that mutates state writes a ledger entry.
