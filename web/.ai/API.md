# API Reference

Base URL: `http://localhost:3000/api` (dev) or configured via `runtimeConfig.public.apiBase`

## Devices

### List All Devices
```
GET /api/devices
```
Returns array of devices with `screenCount` field.

### Get Device
```
GET /api/devices/:id
```
Returns device details with `assignedScreens` array.

### Register Device
```
POST /api/devices
Content-Type: application/json

{
  "id": "e1001-abc123",        // required, device serial
  "name": "Kitchen Display",   // optional, default "Unnamed"
  "variant": "e1001",          // required, "e1001" | "e1002"
  "firmwareVersion": "1.0.0", // optional
  "batteryPct": 85,            // optional, 0-100 or -1 (unknown) or -2 (USB)
  "chargeState": "charging"    // optional, "battery" | "charging" | "full"
}
```
Returns 201 with created device.

### Update Device
```
PATCH /api/devices/:id
Content-Type: application/json

{
  "name": "New Name",
  "batteryPct": 90,
  "chargeState": "full"
}
```
All fields optional. Updates `lastSeen` timestamp.

### Delete Device
```
DELETE /api/devices/:id
```
Returns 204. Also removes all screen assignments for this device.

## Screens

### List All Screens
```
GET /api/screens
```
Returns array of screens with configs parsed as objects.

### Get Screen
```
GET /api/screens/:id
```

### Create Screen
```
POST /api/screens
Content-Type: application/json

{
  "name": "Weather Widget",
  "type": "url",
  "config": {
    "url": "https://example.com/weather",
    "selector": ".forecast"
  }
}
```
Types: `url` | `html` | `weather` | `maintenance`
ID auto-generated as UUID. Returns 201.

### Update Screen
```
PUT /api/screens/:id
Content-Type: application/json

{
  "name": "Updated Name",
  "type": "html",
  "config": { "html": "<div>Hello</div>" }
}
```
Full replacement. All fields required except `id`. Returns updated screen.

### Delete Screen
```
DELETE /api/screens/:id
```
Returns 204. Also removes all device assignments for this screen.

## Device Screens (Assignments)

### List Device Screens
```
GET /api/devices/:id/screens
```
Returns array of assignments with screen details, ordered by `sortOrder`.

### Assign Screens to Device
```
POST /api/devices/:id/screens
Content-Type: application/json

{
  "screens": [
    {
      "screenId": "uuid-of-screen",
      "sortOrder": 0,
      "enabled": true,
      "refreshInterval": 3600
    }
  ]
}
```
Replaces ALL existing assignments for the device. Accepts 1-50 screens.

### Unassign Screen from Device
```
DELETE /api/devices/:id/screens/:screenId
```
Returns 204. Removes single assignment.

## Firmware Endpoint

### Get Page for Device
```
GET /api/device/:id/page/:n
```
Returns the Nth enabled screen for the device (wraps with modulo on total count).

Response:
```json
{
  "deviceId": "e1001-abc123",
  "page": 0,
  "totalScreens": 3,
  "screenIndex": 0,
  "screen": {
    "id": "uuid",
    "name": "Weather",
    "type": "url",
    "config": { "url": "https://..." },
    "refreshInterval": 3600
  }
}
```

Updates device `lastSeen` on each call. Returns 404 if device has no enabled screens.
