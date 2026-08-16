# CodifyLive — Backend

Real-time collaboration platform: chat, audio/video calls, and collaborative coding in the browser.
This repository is the FastAPI backend that powers it.

**Live:** [www.codifylive.com](https://www.codifylive.com) · **API:** [api.codifylive.com](https://api.codifylive.com)
· **API docs:** [OpenAPI reference](https://fulanii.github.io/codify-live-backend/)
· **Frontend repo:** [codify-live-frontend](https://github.com/fulanii/codify-live-frontend)

---

## Why this project exists

It is a working product, but the reason it is built the way it is: I wanted to write the parts most
tutorials skip. Session security that survives a stolen cookie, real-time delivery that still works
when you run more than one server, and running untrusted code without handing over the machine.

Where I have deliberately not built something, it is listed below as out of scope with the reason,
rather than left as an implied gap.

---

## Stack

| Layer      | Choice                                                    |
| ---------- | --------------------------------------------------------- |
| API        | FastAPI 0.141, Python 3.13, Pydantic 2                     |
| Database   | PostgreSQL, SQLAlchemy 2.0 async + asyncpg, Alembic        |
| Auth       | Own JWT access tokens, opaque rotating refresh tokens, Google OAuth 2.0 |
| Passwords  | Argon2id via pwdlib                                        |
| Frontend   | React 18, TypeScript, Vite, Tailwind, React Query          |
| Hosting    | Railway (API + Postgres), Vercel (frontend)                |
| CI         | GitHub Actions — lint, format, migration up/down, OpenAPI publish |

---

## Status

### Shipped

**Authentication**, deployed and in use end to end:

| Endpoint                | Purpose                                              |
| ----------------------- | ---------------------------------------------------- |
| `POST /auth/login`      | Email + password sign-in                              |
| `POST /auth/refresh`    | Rotate the refresh token, issue a new access token    |
| `POST /auth/logout`     | Revoke the current refresh token                      |
| `GET  /auth/me`         | Current user, from the bearer token                   |
| `GET  /auth/login/google`    | Start the Google authorization-code flow          |
| `GET  /auth/google/callback` | Complete it, create the session, redirect to the app |

The design decisions behind these:

- **Access tokens are JWTs, 15 minutes, verified statelessly** — no database round trip to
  authenticate a request. `type` is asserted on decode, so a refresh token cannot be presented as a
  bearer token.
- **Refresh tokens are opaque, not JWTs**, stored only as a SHA-256 hash, in an httpOnly cookie
  scoped to `/auth`. A revocable JWT is a database lookup with extra steps, so the token is just a
  random string whose meaning lives entirely in its row.
- **Rotation with reuse detection.** Every refresh revokes the token presented and issues a new one.
  Revoked rows are kept, not deleted — presenting one again means two parties hold the same token, so
  every session for that user is revoked.
- **Google OAuth written by hand**, not via a library, including `state` for login-CSRF protection
  and full `id_token` verification (signature, issuer, audience, expiry). The client secret never
  reaches the browser, and no access token is ever put in a URL.
- **Login timing does not leak account existence** — the password check runs before account-state
  checks, so a wrong password and an unknown email are indistinguishable.

**Infrastructure:**

- Alembic migrations, one per change, verified reversible in CI
- GitHub Actions gate on `main`: ruff lint, format check, `upgrade head`, `downgrade base`, upgrade again
- OpenAPI schema published to GitHub Pages on every merge
- Frontend deployed on Vercel, API and Postgres on Railway, both on the same registrable domain so
  the session cookie stays `SameSite=Lax`

### In progress

- Friendship and friend requests — atomic accept, canonical-ordered pairs enforced by database
  constraints rather than application checks
- Test suite: pytest + `httpx.AsyncClient` against an ephemeral Postgres, focused on the auth and
  transaction paths

### Planned

| Phase | Feature | The part that is actually interesting |
| ----- | ------- | ------------------------------------- |
| 3 | Chat over REST | Keyset pagination with an index that holds up at 10k+ messages |
| 4 | WebSocket delivery | One multiplexed socket per user; write path stays HTTP |
| 4.5 | Redis pub/sub fan-out | Cross-instance delivery — the thing that makes it horizontally scalable |
| 5–6 | Audio and video calls | WebRTC signaling only; media never touches the server. Short-lived HMAC TURN credentials |
| 7 | Shared editor | Naive last-write-wins first, knowingly |
| 8 | Code execution | Isolated runner, hard timeouts, output caps, rate limits — never in the API process |
| 9 | CRDT collaboration | pycrdt on the server, Yjs in the browser |
| 10 | Terraform + AWS | Production-shaped infrastructure as code |

### Deliberately out of scope

Email verification and password reset (Google already proves the address), MFA, RBAC, an SFU for
group calls (1:1 mesh only — an SFU is a media-engineering project in its own right), and a
hand-rolled OAuth provider.

---

## Architecture notes

**Layering is enforced, not just intended.** Routers handle HTTP, services hold business rules,
repositories touch the database. Services never import FastAPI, so they raise domain errors that get
mapped to status codes at the edge.

**Transactions commit once, at the end of a service call.** Operations that write more than one row —
accepting a friend request, rotating a refresh token — are atomic or they do not happen.

**Invariants live in the database.** Canonical ordering on friendship pairs, partial unique indexes
on pending requests, case-insensitive uniqueness on email. An application-level check races; a
constraint does not.

**Real-time is designed around a seam.** Services publish to an event bus interface rather than
touching the socket registry, so moving from a single process to Redis fan-out across instances is an
adapter and a config flag, not a rewrite.

---

## Running locally

```bash
uv venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env        # fill in database URL, secret key, Google credentials

alembic upgrade head
fastapi dev app/main.py
```

Interactive docs at `http://localhost:8000/docs`.

---

## Author

**Yassine** — [yassinecodes.dev](https://yassinecodes.dev)
