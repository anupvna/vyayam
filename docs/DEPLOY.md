# Deploying

Vyayam runs as one container (FastAPI serving the built React app) on Render's free
plan, with the database on Neon's free plan. Both cost $0.

## 1. Database (Neon)

1. Create a project at neon.tech in **AWS US East (N. Virginia)**, next to the Render
   service (`region: virginia` in `render.yaml`).
2. Click **Connect**, turn **Connection pooling off** (the app runs its own pool, and
   migrations need a direct connection), and copy the string. It looks like
   `postgresql://USER:PASSWORD@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require`.
   If it ends with `&channel_binding=require`, delete that part: the database driver
   doesn't support that option.
3. Keep it somewhere private. It is a password: never commit it.

## 2. App (Render)

1. On render.com: New → Blueprint → pick the GitHub repo. Render reads `render.yaml`.
2. When asked for `DATABASE_URL`, paste the Neon string. For the AI coach, also paste
   `GROQ_API_KEY` and `GEMINI_API_KEY` (or leave them empty for the rule-based coach).
3. Deploy. On start the container applies migrations, then serves the app.
4. Open `https://<your-service>.onrender.com/api/health`. It should show
   `{"status":"ok","database":"ok"}`.

`autoDeploy` is on: every push to `main` builds and goes live in a few minutes.

## Notes

- **Cold starts.** Free Render services sleep after about 15 minutes idle; the first
  request then takes up to a minute. The app works offline once installed, so this
  mostly matters for the first load of the day.
- **Cookies.** Production uses Secure cookies (HTTPS only), which Render provides.
  `COOKIE_SECURE=false` is only for local development.
- **Progress photos** never reach the server, so they are not in the database or
  any backup. Use "Save a copy" in the app to keep them elsewhere.
- **Test the image locally** (optional):

  ```sh
  docker build -t vyayam .
  docker run --rm -p 8000:8000 \
    -e DATABASE_URL=postgresql://vyayam:vyayam@host.docker.internal:5433/vyayam \
    -e COOKIE_SECURE=false vyayam
  ```

  Then open http://localhost:8000.
