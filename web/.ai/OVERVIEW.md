# E-Ink Display Management System

## Overview

A Nuxt 4 web application for managing reTerminal E10xx e-paper displays. Provides device registration, screen template management, screen-to-device assignment with ordering, and a firmware-compatible page-serving endpoint.

## Architecture

```
web/
├── app/
│   ├── app.vue              # Root layout with sidebar navigation
│   ├── app.config.ts        # Nuxt UI config
│   ├── types/index.d.ts     # TypeScript interfaces
│   ├── assets/css/          # Global styles
│   ├── pages/
│   │   ├── index.vue        # Home/dashboard
│   │   ├── devices.vue      # Device management
│   │   ├── screens.vue      # Screen template management
│   │   ├── device-screens.vue # Screen assignment per device
│   │   ├── flasher.vue      # Firmware flashing tool
│   │   └── pages.vue        # Page viewer
│   └── server/              # Nitro server (Nuxt 4: inside app/)
│       ├── api/             # API routes
│       │   ├── devices/     # CRUD for devices
│       │   ├── screens/     # CRUD for screen templates
│       │   └── device/[id]/page/[n].get.ts  # Firmware page endpoint
│       ├── db/
│       │   ├── schema.ts    # Drizzle ORM schema + Zod validators
│       │   └── index.ts     # DB initialization (better-sqlite3)
│       └── plugins/
│           └── db.ts        # Nitro plugin: init DB on startup
└── nuxt.config.ts           # Nuxt + NuxtUI configuration
```

## Database

SQLite via better-sqlite3 + Drizzle ORM.

### Tables

| Table | Purpose |
|-------|---------|
| `devices` | Registered e-ink display devices |
| `screens` | Reusable screen templates (URL, HTML, weather, maintenance) |
| `device_screens` | Many-to-many join: device ↔ screen with ordering |

### Key Design Decisions

- **Screen configs stored as JSON** — flexible schema per screen type
- **Device IDs are user-assigned** (e.g., serial numbers), not UUIDs
- **Screen template IDs are UUIDs** — auto-generated on creation
- **Sort order on assignments** — determines page rotation order on device
- **Refresh interval per assignment** — each screen can have its own refresh rate

## API Philosophy

- All API routes return JSON
- Proper HTTP status codes: 200, 201, 204, 400, 404, 409
- Zod validation on all write endpoints
- Foreign key cascading handled manually in delete endpoints
- No authentication (designed for local network use)

## Firmware Integration

E-ink devices call `GET /api/device/{deviceId}/page/{n}` to get page content. The endpoint:
1. Looks up the device by ID
2. Gets assigned screens sorted by `sort_order`
3. Filters to enabled screens only
4. Returns screen N (wrapping with modulo)
5. Updates device `last_seen` timestamp

The device firmware cycles through pages by incrementing N on each refresh.
