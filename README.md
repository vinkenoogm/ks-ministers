# ks-ministers | MVP

**Scope:** A public Streamlit signup form matching the K398 November prep Google Form, with conditional day selection, availability reuse, input validation, and persistent Neon PostgreSQL submissions. **No admin/dashboard/scheduler.**

## Setup

1. Create a new GitHub repository `ks-ministers`; upload `app.py`, `requirements.txt`, `.gitignore`, `README.md`, and `.streamlit/secrets.toml.example`.
2. In Streamlit Community Cloud, deploy the new repository with `app.py` as the entrypoint.
3. Under the new app's **Settings → Secrets**, set `DATABASE_URL = "postgresql://..."` to your **existing Neon connection string**. Do **not** push a real `secrets.toml` to GitHub.
4. Visit the deployed app and **submit one test entry**. Verify the row exists in Neon before sharing the link with the server.
5. Optionally delete the test row directly in Neon using its submission reference.

The app creates only the table `ks_minister_requests` (UUID id, timestamp, username/alliance, in-game ID, JSONB payload). It never touches tables of other applications. Your Neon role must be allowed to create a table. If it cannot, create the table manually using the SQL below.

```sql
CREATE TABLE IF NOT EXISTS ks_minister_requests (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    username_alliance TEXT NOT NULL,
    in_game_id TEXT,
    payload JSONB NOT NULL
);
```

For a quick export, use Neon's SQL editor to query `SELECT * FROM ks_minister_requests ORDER BY created_at;` and export the result.

## Form behavior

- Monday (Nov 2): construction, TG, TTG, speedup days.
- Thursday (Nov 5): troop training, speedup days.
- Friday (Nov 6): research, speedup days, dust.
- All days: select UTC times or copy from a **previously selected** day, preventing invalid references.
- Each `HH:15` selection expands to `HH:15` and `HH:45`. First/last `23:45` are separate, 15-minute entries.
- The entire submission is saved in one database transaction. Upon success, the app shows a submission reference.

## Deliberate MVP limitations

- No accounts or editing after submit. Players could submit twice; reconcile duplicates offline using name/ID and submission date.
- No admin panel, live dashboards, scheduling algorithm, automated Discord messages, or scoring.
- Public endpoint: test and share deliberately. Do not store sensitive secrets in form submissions.
- The submitted availability is UTC and refers to the November 2026 dates only. Confirm Kingshot event/reset boundaries before launch.
