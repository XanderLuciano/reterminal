export interface Device {
  id: string
  name: string
  variant: string
  firmwareVersion: string | null
  batteryPct: number | null
  chargeState: string | null
  lastSeen: number | null
  createdAt: number
  screenCount?: number
  assignedScreens?: ScreenConfig[]
}

export interface Screen {
  id: string
  name: string
  type: string
  config: Record<string, unknown>
  thumbData: string | null
  createdAt: number
  updatedAt: number
}

export interface ScreenConfig {
  id: string
  name: string
  type: string
  config: Record<string, unknown>
  enabled: boolean
  refresh_interval?: number
  sortOrder?: number
}

export interface DeviceScreenAssignment {
  assignmentId: string
  deviceId: string
  screenId: string
  sortOrder: number
  enabled: boolean
  refreshInterval: number
  screen: {
    name: string
    type: string
    config: Record<string, unknown>
  }
}
