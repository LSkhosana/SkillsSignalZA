# SkillSignalZA

Universal customer application for SkillSignalZA. This Expo app is the client shell for web, Android, and iOS. It does not own assessment, scoring, payment fulfillment, or report assembly.

## Supported platforms

- Web
- Android
- iOS

## Requirements

- Node.js 22.13 or later
- npm 10 or later

## Installation

From this `Main/` directory:

```bash
npm ci
```

## Environment setup

1. Copy `.env.example` to `.env`.
2. Replace the placeholders with client-safe values for your local environment.

| Variable | Purpose |
| --- | --- |
| `EXPO_PUBLIC_API_URL` | Base URL for the SkillSignalZA API in `Server/` |
| `EXPO_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Supabase publishable (anon) key |

The app boots without these values. They are validated only when a feature actually reads them.

Never place real secrets in variables prefixed with `EXPO_PUBLIC_`. Anything with that prefix is embedded in the client bundle. Do not put a Supabase service-role key, database password, Paystack secret key, or other private credential in this application.

## Customer flow

```text
/                               landing and track selection
/assessment/new                 CV + optional links
/assessment/[id]/preview        readiness.preview.v1
/sign-up and /sign-in           Supabase email/password
/assessment/[id]/payment        claim, Paystack checkout, wait for unlock
/assessment/[id]/report         readiness.report.v1
```

The client never scores assessments, calls Paystack APIs, or reads Supabase tables. Payment amount, currency, product, and email are chosen by `Server/`. Fulfillment is detected only by `GET /api/v1/assessments/{id}/report`.

## Development commands

```bash
npm start          # Start Expo
npm run web        # Web development
npm run android    # Android development
npm run ios        # iOS development
npm test           # Jest + jest-expo
npm run lint       # Lint
npm run typecheck  # TypeScript type checking
npm run export:web # Static web export to dist/
```

## Tests

Frontend tests use **Jest** with the **jest-expo** preset and **React Native Testing Library**. Automated tests mock HTTP and Supabase Auth. They never call live Supabase or Paystack.

## Web export

```bash
npm run export:web
```

The static output is written to `dist/`.

## Assessment and scoring

`Server/` owns the deterministic assessment engine, scoring, ownership, Paystack checkout, webhook fulfillment, entitlement, and report assembly. Do not implement scoring or payment authority in `Main/`.
