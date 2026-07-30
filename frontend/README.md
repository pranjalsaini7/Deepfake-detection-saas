# Veritas Frontend (Next.js 16)

The frontend application for VERITAS — Deepfake Detection Platform.

---

## 🎨 Features & Architecture

- **Root Landing Page (`/`)**: Rewritten in `next.config.mjs` to serve `public/index-veritas.html`. Includes:
  - Off-white cinematic theme (`#f0efe9`).
  - Interactive warm-orange cursor-following Canvas glow.
  - Live Indian Standard Time (**IST**) header clock.
  - Lenis smooth scroll & scroll-reveal animations.
  - Diagnostic workspace drag & drop uploader calling backend `/detect`.
- **Authentication Routes**: `/login` and `/signup` powered by Supabase Auth (`@/components/AuthProvider.js`).
- **Protected Dashboard**: `/dashboard` guarded by AuthProvider context.

---

## 🛠️ Development

```bash
# Install dependencies
npm install

# Start Next.js dev server on port 3000
npm run dev
```

---

## 🚀 Vercel Deployment

Set the following Environment Variables in your Vercel Project Settings:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
