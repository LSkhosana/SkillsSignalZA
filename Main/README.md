# SkillSignalZA

Universal customer application for SkillSignalZA. This Expo app is the client shell for web, Android, and iOS. It does not own assessment or scoring logic.

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
npm install
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

Never place real secrets in variables prefixed with `EXPO_PUBLIC_`. Anything with that prefix is embedded in the client bundle. Do not put a Supabase service-role key, database password, or other private credential in this application.

## Development commands

```bash
npm start          # Start Expo
npm run web        # Web development
npm run android    # Android development
npm run ios        # iOS development
npm run lint       # Lint
npm run typecheck  # TypeScript type checking
```

## Web export

```bash
npx expo export --platform web
```

The static output is written to `dist/`.

## Assessment and scoring

`Server/` owns the deterministic assessment engine, scoring, and related API logic. Do not implement scoring in `Main/`.
