<script setup lang="ts">
const config = useRuntimeConfig()
const API_BASE = config.public.apiBase
const BUILD_POLL_MAX_S = 600  // 10 minute max poll

// ── Device & form state ──
const device = ref<'e1001' | 'e1002'>('e1002')
const wifiSsid = ref('')
const wifiPass = ref('')
const dashboardUrl = ref('')
const deepSleep = ref(60)
const bleTimeout = ref(10)
const healthInterval = ref(6)
const selectTimeout = ref(30)
const bleName = ref('')
const enableBeeps = ref(true)
const showPassword = ref(false)
const showAdvanced = ref(false)

const urlPreview = computed(() => {
  const base = dashboardUrl.value || 'http://YOUR_SERVER_IP:8088'
  return base.replace(/\/+$/, '') + (device.value === 'e1002' ? '/dashboard.bin' : '/dashboard-bw.bin')
})

// ── Build state ──
const building = ref(false)
const buildStatus = ref('')
const buildMessage = ref('')
const buildLog = ref('')
const buildId = ref('')
const firmwareUrl = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null
let buildStartMs = 0

// ── Quick flash ──
const qfStatus = ref('')
const qfLog = ref('')

// ── BLE trigger ──
const BLE_UUIDS: Record<string, { deviceName: string; serviceUUID: string; triggerUUID: string }> = {
  e1002: {
    deviceName: 'E1002-Dashboard',
    serviceUUID: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    triggerUUID: 'b2c3d4e5-f6a7-8901-bcde-f12345678901'
  },
  e1001: {
    deviceName: 'E1001-Dashboard',
    serviceUUID: 'c3d4e5f6-a7b8-9012-cdef-123456789012',
    triggerUUID: 'd4e5f6a7-b8c9-0123-defa-234567890123'
  }
}

const bleStatus = ref('')
const bleLogText = ref('')
const bleActive = ref(false)

// ── Build ──
async function startBuild() {
  building.value = true
  buildStatus.value = 'building'
  buildMessage.value = 'Starting build...'
  buildLog.value = ''
  firmwareUrl.value = ''

  try {
    const config: Record<string, unknown> = {
      device: device.value,
      wifi_ssid: wifiSsid.value,
      wifi_password: wifiPass.value,
      dashboard_url: dashboardUrl.value,
      deep_sleep_seconds: deepSleep.value,
      advertise_timeout_s: bleTimeout.value,
      health_interval_hours: healthInterval.value,
      select_timeout_s: selectTimeout.value,
      enable_beeps: enableBeeps.value
    }
    if (bleName.value) config.ble_device_name = bleName.value

    const res = await fetch(`${API_BASE}/build`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })
    const data = await res.json()
    buildId.value = data.build_id

    // Poll for status
    buildStartMs = Date.now()
    pollTimer = setInterval(pollBuild, 1000)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    buildStatus.value = 'error'
    buildMessage.value = `Failed to start build: ${msg}`
    building.value = false
  }
}

async function pollBuild() {
  // Timeout after BUILD_POLL_MAX_S
  if (Date.now() - buildStartMs > BUILD_POLL_MAX_S * 1000) {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    buildStatus.value = 'error'
    buildMessage.value = 'Build timed out after 10 minutes'
    building.value = false
    return
  }
  try {
    const res = await fetch(`${API_BASE}/build/${buildId.value}`)
    const data = await res.json()

    if (data.lines) {
      buildLog.value = data.lines.slice(-80).join('\n')
    }
    buildMessage.value = data.message || ''
    buildStatus.value = data.status

    if (data.status === 'done') {
      building.value = false
      firmwareUrl.value = data.files?.merged || ''
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    } else if (data.status === 'error') {
      building.value = false
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    }
  } catch {
    // polling will retry
  }
}

// ── Quick flash ──
async function quickFlash(variant: string) {
  qfStatus.value = 'fetching'
  qfLog.value = 'Downloading pre-built firmware...'

  try {
    const res = await fetch(`${API_BASE}/prebuilt/${variant}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const blob = await res.blob()
    const sizeKB = (blob.size / 1024).toFixed(0)
    qfLog.value += `\nGot ${sizeKB} KB firmware`

    // Trigger browser download
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `eink-${variant}-factory.bin`
    a.click()
    URL.revokeObjectURL(url)

    qfStatus.value = 'done'
    qfLog.value += `\nSaved eink-${variant}-factory.bin (${sizeKB} KB)`
    qfLog.value += '\nFlash: esptool.py --port PORT write_flash 0x0 firmware.bin'
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    qfStatus.value = 'error'
    qfLog.value += `\nERROR: ${msg}`
  }
}

// ── Firmware download ──
function downloadFirmware() {
  if (firmwareUrl.value) {
    window.open(firmwareUrl.value, '_blank')
  }
}

// ── BLE ──
async function triggerBLE() {
  const config = BLE_UUIDS[device.value]
  bleLogText.value = ''
  bleActive.value = true
  let btDevice: any = null

  try {
    if (!(navigator as any).bluetooth) {
      bleStatus.value = 'Web Bluetooth not available. Use Chrome or Edge.'
      bleActive.value = false
      return
    }

    bleLogText.value = 'Scanning for ' + config.deviceName + '...'

    btDevice = await (navigator as any).bluetooth.requestDevice({
      filters: [
        { name: config.deviceName },
        { services: [config.serviceUUID] }
      ],
      optionalServices: [config.serviceUUID]
    })

    bleLogText.value += '\nConnecting GATT...'
    const server = await btDevice.gatt.connect()
    const service = await server.getPrimaryService(config.serviceUUID)
    const characteristic = await service.getCharacteristic(config.triggerUUID)
    await characteristic.writeValueWithoutResponse(new Uint8Array([0x01]))

    bleStatus.value = 'Trigger sent!'
    bleLogText.value += '\n✓ Display will refresh within 60s'
    setTimeout(() => { bleActive.value = false }, 3000)

  } catch (e: unknown) {
    const err = e as { name?: string; message?: string }
    bleLogText.value += '\n' + (err.name || 'Error') + ': ' + (err.message || '')
    bleStatus.value = 'BLE trigger failed: ' + (err.message || '')
    bleActive.value = false
  } finally {
    if (btDevice?.gatt?.connected) btDevice.gatt.disconnect()
  }
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="p-6 max-w-2xl">
    <h1 class="text-2xl font-bold mb-2">Flasher</h1>
    <p class="text-muted mb-6">Configure settings and flash your reTerminal E10xx from the browser.</p>

    <!-- Device -->
    <UCard class="mb-4">
      <template #header>
        <span class="font-semibold">Device</span>
      </template>
      <div class="flex gap-4">
        <label
          v-for="d in [{ id: 'e1002', label: 'E1002', desc: 'Spectra 6 · Color' }, { id: 'e1001', label: 'E1001', desc: 'Monochrome · BW' }]"
          :key="d.id"
          class="flex-1 cursor-pointer"
        >
          <input type="radio" :value="d.id" v-model="device" class="sr-only">
          <div
            class="p-3 rounded-lg border-2 text-center transition-colors"
            :class="device === d.id ? 'border-primary-500 bg-primary-50 dark:bg-primary-950' : 'border-gray-200 dark:border-gray-700'"
          >
            <span class="font-semibold text-sm" :class="device === d.id ? 'text-primary-600' : ''">{{ d.label }}</span>
            <span class="block text-xs text-muted mt-1">{{ d.desc }}</span>
          </div>
        </label>
      </div>
    </UCard>

    <!-- Network -->
    <UCard class="mb-4">
      <template #header>
        <span class="font-semibold">Network</span>
      </template>
      <div class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <UFormField label="WiFi SSID" required>
            <UInput v-model="wifiSsid" placeholder="MyNetwork" maxlength="32" />
          </UFormField>
          <UFormField label="WiFi Password" required>
            <UInput
              v-model="wifiPass"
              :type="showPassword ? 'text' : 'password'"
              placeholder="••••••••"
              maxlength="63"
              :ui="{ trailing: 'pr-0' }"
            >
              <template #trailing>
                <UButton
                  color="neutral"
                  variant="link"
                  :icon="showPassword ? 'i-lucide-eye-off' : 'i-lucide-eye'"
                  @click="showPassword = !showPassword"
                />
              </template>
            </UInput>
          </UFormField>
        </div>
        <UFormField label="Dashboard Server URL" required>
          <UInput v-model="dashboardUrl" placeholder="http://192.168.1.100:8088" />
          <template #help>
            ESP32 fetches: <code class="text-xs">{{ urlPreview }}</code>
          </template>
        </UFormField>
      </div>
    </UCard>

    <!-- Timing -->
    <UCard class="mb-4">
      <template #header>
        <span class="font-semibold">Timing</span>
      </template>
      <div class="grid grid-cols-2 gap-4">
        <UFormField label="Deep Sleep (seconds)">
          <UInput v-model.number="deepSleep" type="number" :min="10" :max="3600" />
          <template #help>Time between auto-refreshes</template>
        </UFormField>
        <UFormField label="BLE Advertise (seconds)">
          <UInput v-model.number="bleTimeout" type="number" :min="5" :max="120" />
          <template #help>How long BLE listens for triggers</template>
        </UFormField>
        <UFormField label="Health Refresh (hours)">
          <UInput v-model.number="healthInterval" type="number" :min="1" :max="48" />
          <template #help>Full WiFi refresh interval</template>
        </UFormField>
        <UFormField label="Button Select Timeout (sec)">
          <UInput v-model.number="selectTimeout" type="number" :min="5" :max="120" />
          <template #help>Button menu active duration</template>
        </UFormField>
      </div>
    </UCard>

    <!-- Advanced -->
    <div class="text-center mb-4">
      <UButton
        color="neutral"
        variant="ghost"
        :label="showAdvanced ? 'Hide advanced options ▴' : 'Show advanced options ▾'"
        @click="showAdvanced = !showAdvanced"
      />
    </div>
    <UCard v-if="showAdvanced" class="mb-4">
      <template #header>
        <span class="font-semibold">Advanced</span>
      </template>
      <div class="space-y-4">
        <UFormField label="BLE Device Name">
          <UInput v-model="bleName" :placeholder="device === 'e1001' ? 'E1001-Dashboard' : 'E1002-Dashboard'" maxlength="20" />
        </UFormField>
        <UCheckbox v-model="enableBeeps" label="Enable buzzer beeps" />
      </div>
    </UCard>

    <!-- Quick Flash (download only) -->
    <UCard class="mb-4">
      <template #header>
        <span class="font-semibold">Pre-Built Firmware</span>
      </template>
      <p class="text-sm text-muted mb-3">Download and flash manually (no build wait). Mock credentials — shows error screen on boot.</p>
      <div class="flex gap-3">
        <UButton color="primary" variant="outline" block @click="quickFlash('e1002')">⬇ E1002 Color</UButton>
        <UButton color="primary" variant="outline" block @click="quickFlash('e1001')">⬇ E1001 BW</UButton>
      </div>
      <p v-if="qfStatus" class="mt-3 text-sm" :class="qfStatus === 'error' ? 'text-red-500' : qfStatus === 'done' ? 'text-green-500' : 'text-yellow-500'">
        {{ qfStatus === 'fetching' ? 'Downloading...' : qfStatus === 'done' ? 'Download ready' : 'Error' }}
      </p>
      <pre v-if="qfLog" class="mt-2 text-xs text-muted bg-gray-100 dark:bg-gray-800 p-3 rounded max-h-40 overflow-auto">{{ qfLog }}</pre>
    </UCard>

    <!-- Build -->
    <UCard class="mb-4">
      <template #header>
        <span class="font-semibold">Build Firmware</span>
      </template>
      <UButton
        color="primary"
        block
        :loading="building"
        :disabled="!wifiSsid || !wifiPass || !dashboardUrl"
        @click="startBuild"
      >
        {{ building ? 'Building...' : 'Build & Download' }}
      </UButton>

      <div v-if="buildStatus" class="mt-4">
        <p class="text-sm" :class="{
          'text-yellow-500': buildStatus === 'building' || buildStatus === 'queued',
          'text-green-500': buildStatus === 'done',
          'text-red-500': buildStatus === 'error'
        }">
          {{ buildMessage }}
        </p>

        <!-- Progress bar -->
        <UProgress
          v-if="buildStatus === 'building' || buildStatus === 'queued'"
          animation="carousel"
          class="mt-2"
        />

        <pre
          v-if="buildLog"
          class="mt-2 text-xs text-muted bg-gray-100 dark:bg-gray-800 p-3 rounded max-h-60 overflow-auto"
        >{{ buildLog }}</pre>

        <UButton
          v-if="buildStatus === 'done' && firmwareUrl"
          color="primary"
          variant="outline"
          block
          class="mt-3"
          @click="downloadFirmware"
        >
          Download Firmware
        </UButton>
      </div>
    </UCard>

    <!-- BLE Trigger -->
    <UCard>
      <template #header>
        <span class="font-semibold">BLE Trigger</span>
      </template>
      <p class="text-sm text-muted mb-3">Send a BLE trigger to force a display refresh.</p>
      <UButton
        color="neutral"
        variant="outline"
        block
        :loading="bleActive"
        @click="triggerBLE"
      >
        {{ bleActive ? 'Connecting...' : 'Connect & Trigger' }}
      </UButton>
      <p v-if="bleStatus" class="mt-3 text-sm" :class="bleStatus.includes('failed') || bleStatus.includes('not available') ? 'text-red-500' : 'text-green-500'">
        {{ bleStatus }}
      </p>
      <pre v-if="bleLogText" class="mt-2 text-xs text-muted bg-gray-100 dark:bg-gray-800 p-3 rounded max-h-40 overflow-auto">{{ bleLogText }}</pre>
    </UCard>
  </div>
</template>
