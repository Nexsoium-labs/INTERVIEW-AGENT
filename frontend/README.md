# ZT-ATE Frontend

Next.js operator and candidate console for the split-plane interview agent backend.

## Routes

- `/`: landing page
- `/operator/[sessionId]`: operator console with technical verdict, evidence, overlay, and milestones
- `/candidate/[sessionId]`: candidate-safe view without evaluator internals

## Environment

Create `.env.local` with:

```bash
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000/api
```

## Run

```bash
npm install
npm run dev
```
