<script setup lang="ts">
import { nextTick } from 'vue'

const config = useRuntimeConfig()
const API_BASE = config.public.apiBase
const BUILD_POLL_MAX_S = 600  // 10 minute max poll

// ── Device & form state ──
const device = ref<'e1001' | 'e1002'>('e1002')
const wifiSsid = ref('')
const wifiPass = ref('')
const dashboardUrl = ref(window?.location?.origin || '')
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

// ── Console helpers ──
function ts() { return new Date().toLocaleTimeString() }

function consoleLog(lines: Ref<string[]>, el: Ref<HTMLElement | null>, msg: string, max = 200) {
  lines.value.push(`[${ts()}] ${msg}`)
  if (lines.value.length > max) lines.value = lines.value.slice(-max)
  nextTick(() => { if (el.value) el.value.scrollTop = el.value.scrollHeight })
}
function consoleClear(lines: Ref<string[]>) { lines.value = [] }

// ── Console refs ──
const buildLines = ref<string[]>([])
const buildEl = ref<HTMLElement | null>(null)
const qfLines = ref<string[]>([])
const qfEl = ref<HTMLElement | null>(null)
const bleLines = ref<string[]>([])
const bleEl = ref<HTMLElement | null>(null)
const flashLines = ref<string[]>([])
const flashEl = ref<HTMLElement | null>(null)

// ── Build state ──
const building = ref(false)
const buildStatus = ref('')
const buildMessage = ref('')
const buildId = ref('')
const firmwareUrl = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null
let buildStartMs = 0
let lastShownCount = 0

// ── Pre-built info ──
const prebuiltInfo = ref<Record<string, { size: number; available: boolean; file: string; note?: string }>>({})

async function loadPrebuiltInfo() {
  try {
    const res = await fetch(`${API_BASE}/api/prebuilt`)
    prebuiltInfo.value = await res.json()
  } catch { /* server may be offline */ }
}

const prebuiltLabel = computed(() => (variant: string) => {
  const info = prebuiltInfo.value[variant]
  if (!info || !info.available) return `${variant.toUpperCase()} (unavailable)`
  return `${variant.toUpperCase()} (${(info.size / 1024).toFixed(0)} KB)`
})

const prebuiltDisabled = computed(() => (variant: string) => {
  const info = prebuiltInfo.value[variant]
  return !info || !info.available
})

// ── Quick flash ──
const qfStatus = ref('')

// ── Local file upload ──
const localFileName = ref('')
const localBinSize = ref('')
let localBinary: Uint8Array | null = null

function handleLocalFile(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  localFileName.value = file.name
  localBinSize.value = (file.size / 1024).toFixed(1) + ' KB'

  const reader = new FileReader()
  reader.onload = () => {
    localBinary = new Uint8Array(reader.result as ArrayBuffer)
    consoleLog(flashLines, flashEl, `Loaded local file: ${file.name} (${localBinSize.value})`)
    showFlashCard()
  }
  reader.readAsArrayBuffer(file)
}

function clearLocalFile() {
  localBinary = null
  localFileName.value = ''
  localBinSize.value = ''
  const input = document.getElementById('local-file-input') as HTMLInputElement
  if (input) input.value = ''
  if (!firmwareUrl.value) flashCardVisible.value = false
}

// ── Flash to device ──
const flashCardVisible = ref(false)
const flashCardRef = ref<HTMLElement | null>(null)
const flashSource = ref('') // 'build' | 'local'
const flashSourceDetail = ref('')
const flashStatus = ref('')
const flashing = ref(false)
const flashProgress = ref(0)
let flashPort: SerialPort | null = null

function showFlashCard(source?: string, detail?: string) {
  flashCardVisible.value = true
  if (source) flashSource.value = source
  if (detail) flashSourceDetail.value = detail
}

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
const bleActive = ref(false)

// ── Build ──
async function startBuild() {
  building.value = true
  buildStatus.value = 'building'
  buildMessage.value = 'Starting build...'
  consoleClear(buildLines)
  lastShownCount = 0
  firmwareUrl.value = ''
  flashCardVisible.value = false

  try {
    const cfg: Record<string, unknown> = {
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
    if (bleName.value) cfg.ble_device_name = bleName.value

    consoleLog(buildLines, buildEl, `Build started for ${device.value.toUpperCase()}`)

    const res = await fetch(`${API_BASE}/api/build`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg)
    })
    const data = await res.json()
    buildId.value = data.build_id
    consoleLog(buildLines, buildEl, `Build ID: ${data.build_id}`)

    buildStartMs = Date.now()
    pollTimer = setInterval(pollBuild, 1000)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    consoleLog(buildLines, buildEl, `ERROR: ${msg}`)
    buildStatus.value = 'error'
    buildMessage.value = `Failed to start build: ${msg}`
    building.value = false
  }
}

async function pollBuild() {
  if (Date.now() - buildStartMs > BUILD_POLL_MAX_S * 1000) {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    buildStatus.value = 'error'
    buildMessage.value = 'Build timed out after 10 minutes'
    building.value = false
    return
  }
  try {
    const res = await fetch(`${API_BASE}/api/build/${buildId.value}`)
    const data = await res.json()

    if (data.lines && data.lines.length > lastShownCount) {
      for (const line of data.lines.slice(lastShownCount)) {
        consoleLog(buildLines, buildEl, line)
      }
      lastShownCount = data.lines.length
    }
    buildMessage.value = data.message || ''
    buildStatus.value = data.status

    if (data.status === 'done') {
      building.value = false
      firmwareUrl.value = data.files?.merged || ''
      const sizeKB = ((data.files?.merged_size || 0) / 1024).toFixed(0)
      consoleLog(buildLines, buildEl, `Build complete! ${sizeKB} KB ready to flash.`)
      showFlashCard('build', sizeKB + ' KB')
      nextTick(() => { flashCardRef.value?.scrollIntoView({ behavior: 'smooth', block: 'center' }) })
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    } else if (data.status === 'error') {
      building.value = false
      consoleLog(buildLines, buildEl, `BUILD ERROR: ${data.message}`)
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    }
  } catch {
    // polling will retry
  }
}

// ── Firmware download ──
function downloadFirmware() {
  if (firmwareUrl.value) {
    window.open(firmwareUrl.value, '_blank')
  }
}

// ── Quick flash ──
async function quickFlash(variant: string) {
  qfStatus.value = 'fetching'
  consoleClear(qfLines)
  consoleLog(qfLines, qfEl, 'Fetching pre-built image for ' + variant.toUpperCase() + '...')

  try {
    const res = await fetch(`${API_BASE}/prebuilt/${variant}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const blob = await res.blob()
    const binary = new Uint8Array(await blob.arrayBuffer())
    const sizeKB = (blob.size / 1024).toFixed(0)
    consoleLog(qfLines, qfEl, `Downloaded ${sizeKB} KB`)

    // Try Web Serial flash directly
    if (!(navigator as any).serial) {
      // Fallback: download only
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `eink-${variant}-factory.bin`
      a.click()
      URL.revokeObjectURL(url)
      qfStatus.value = 'done'
      consoleLog(qfLines, qfEl, `Saved eink-${variant}-factory.bin (${sizeKB} KB)`)
      consoleLog(qfLines, qfEl, 'Flash: esptool.py --port PORT write_flash 0x0 firmware.bin')
      return
    }

    // Release stale port, request fresh
    if (flashPort) {
      try { await flashPort.close() } catch (_) { /* best-effort */ }
      flashPort = null
    }

    consoleLog(qfLines, qfEl, 'Requesting serial port...')
    try {
      flashPort = await (navigator as any).serial.requestPort()
    } catch (e: any) {
      if (e.name === 'NotFoundError' || e.name === 'AbortError') {
        consoleLog(qfLines, qfEl, 'Cancelled — no port selected')
        qfStatus.value = 'done'
        return
      }
      throw e
    }

    consoleLog(qfLines, qfEl, `Flashing ${variant.toUpperCase()}...`)
    await doFlash(binary, variant.toUpperCase(), {
      log: (msg) => consoleLog(qfLines, qfEl, msg),
      progress: (_pct) => {},
      onComplete: () => {
        qfStatus.value = 'done'
        consoleLog(qfLines, qfEl, 'Flash complete! Device is rebooting.')
      },
    })

  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    consoleLog(qfLines, qfEl, `ERROR: ${msg}`)
    qfStatus.value = 'error'
  }
}

// ── Flash to device ──
async function startFlash() {
  if (flashing.value) return
  flashing.value = true
  flashStatus.value = 'Connecting...'
  flashProgress.value = 0
  consoleClear(flashLines)
  consoleLog(flashLines, flashEl, 'Preparing to flash...')

  // Release previous session
  if (flashPort) {
    try { await flashPort.close() } catch (_) { /* best-effort */ }
    flashPort = null
  }

  try {
    if (!(navigator as any).serial) {
      throw new Error('Web Serial API not available. Use Chrome or Edge.')
    }

    consoleLog(flashLines, flashEl, 'Requesting serial port — select your ESP32 device...')
    flashPort = await (navigator as any).serial.requestPort()

    const info = flashPort!.getInfo()
    const deviceLabel = (info as any).usbProductName || 'ESP32-S3'
    consoleLog(flashLines, flashEl, 'Connected to ' + deviceLabel)
    flashStatus.value = 'Connected to ' + deviceLabel + '. Flashing...'

    // Get firmware binary — local file takes priority
    let binary: Uint8Array
    if (localBinary) {
      binary = localBinary
      consoleLog(flashLines, flashEl, `Using local file (${(binary.length / 1024).toFixed(1)} KB)`)
    } else if (firmwareUrl.value) {
      consoleLog(flashLines, flashEl, 'Downloading firmware...')
      const resp = await fetch(firmwareUrl.value)
      const buf = await resp.arrayBuffer()
      binary = new Uint8Array(buf)
      consoleLog(flashLines, flashEl, `Firmware: ${(binary.length / 1024).toFixed(1)} KB`)
    } else {
      throw new Error('No firmware available — build or load a file first')
    }

    await doFlash(binary, deviceLabel, {
      log: (msg) => consoleLog(flashLines, flashEl, msg),
      progress: (pct) => {
        flashProgress.value = pct
        flashStatus.value = `Flashing: ${pct}%`
      },
      onComplete: () => {
        flashProgress.value = 100
        flashStatus.value = 'Flash complete! Device is rebooting.'
        consoleLog(flashLines, flashEl, 'SUCCESS: Flash complete!')
      },
    })

  } catch (e: unknown) {
    const err = e as { name?: string; message?: string }
    const msg = err.message || ''

    if (flashPort) {
      try { await flashPort.close() } catch (_) { /* best-effort */ }
      flashPort = null
    }

    if (msg.includes('No port selected') || err.name === 'AbortError') {
      consoleLog(flashLines, flashEl, 'Cancelled — no port selected')
      flashStatus.value = 'Flash cancelled'
    } else {
      consoleLog(flashLines, flashEl, `FLASH ERROR: ${msg}`)
      flashStatus.value = 'Flash failed: ' + msg

      if (msg.includes('timeout') || msg.includes('Failed to connect')) {
        consoleLog(flashLines, flashEl, 'HINT: Auto-reset may have failed. Try manual download mode:')
        consoleLog(flashLines, flashEl, '  Hold BOOT → press RESET → release BOOT.')
      }
    }
  } finally {
    flashing.value = false
  }
}

// ── Shared flash engine (esptool-js) ──
async function doFlash(
  binary: Uint8Array,
  label: string,
  cb: { log: (m: string) => void; progress: (p: number) => void; onComplete: () => void }
) {
  // Dynamic import esptool-js (external URL, Vite passes through in dev)
  const espMod = await import('https://unpkg.com/esptool-js@0.6.0/bundle.js') as any
  const ESPLoader = espMod.ESPLoader
  const Transport = espMod.Transport

  const baudRates = [921600, 115200]
  let lastError: Error | null = null

  for (let i = 0; i < baudRates.length; i++) {
    const baud = baudRates[i]
    let transport: any = null
    let loader: any = null

    if (i > 0) {
      cb.log(`⚠ Serial error — retrying at ${baud / 1000} kbps...`)
      try { await flashPort!.close() } catch (_) { /* best-effort */ }
      await new Promise(r => setTimeout(r, 1000))
    }

    try {
      transport = new Transport(flashPort)
      loader = new ESPLoader({
        transport,
        baudrate: baud,
        terminal: { clean: () => {}, writeLine: (m: string) => cb.log('ESP: ' + m), write: () => {} },
      })

      cb.log(i === 0 ? 'Entering bootloader...' : 'Re-entering bootloader...')
      await loader.main()
      cb.log(`Chip: ${loader.chipName} — flashing at ${baud / 1000} kbps`)

      await loader.writeFlash({
        fileArray: [{ data: binary, address: 0x0 }],
        flashSize: 'keep', flashMode: 'keep', flashFreq: 'keep',
        eraseAll: false, compress: true,
        reportProgress: (_fi: number, written: number, total: number) => {
          cb.progress(Math.round((written / total) * 100))
        },
      })

      cb.log('Done! Resetting device...')
      await loader.after()

      try { await transport.disconnect() } catch (_) { /* best-effort */ }
      try { await flashPort!.close() } catch (_) { /* best-effort */ }
      flashPort = null

      cb.onComplete()
      return

    } catch (innerErr: any) {
      if (transport) {
        try { await transport.disconnect() } catch (_) { /* best-effort */ }
      }
      try { await flashPort!.close() } catch (_) { /* best-effort */ }
      transport = null
      loader = null
      lastError = innerErr

      const msg: string = innerErr.message || ''
      const isSerial = msg.includes('stream stopped') || msg.includes('noise')
        || msg.includes('corruption') || msg.includes('Invalid head')
        || msg.includes('Bad size')

      if (isSerial && i < baudRates.length - 1) continue
      throw innerErr
    }
  }
  throw lastError || new Error('Flash failed at all baud rates')
}

// ── BLE ──
async function triggerBLE() {
  const bconfig = BLE_UUIDS[device.value]
  consoleClear(bleLines)
  bleActive.value = true
  let btDevice: any = null

  try {
    if (!(navigator as any).bluetooth) {
      bleStatus.value = 'Web Bluetooth not available. Use Chrome or Edge.'
      bleActive.value = false
      return
    }

    consoleLog(bleLines, bleEl, 'Scanning for ' + bconfig.deviceName + '...')

    btDevice = await (navigator as any).bluetooth.requestDevice({
      filters: [
        { name: bconfig.deviceName },
        { services: [bconfig.serviceUUID] }
      ],
      optionalServices: [bconfig.serviceUUID]
    })

    consoleLog(bleLines, bleEl, 'Connecting GATT...')
    const server = await btDevice.gatt.connect()
    const service = await server.getPrimaryService(bconfig.serviceUUID)
    const characteristic = await service.getCharacteristic(bconfig.triggerUUID)
    await characteristic.writeValueWithoutResponse(new Uint8Array([0x01]))

    bleStatus.value = 'Trigger sent!'
    consoleLog(bleLines, bleEl, '✓ Display will refresh within 60s')
    setTimeout(() => { bleActive.value = false }, 3000)

  } catch (e: unknown) {
    const err = e as { name?: string; message?: string }
    consoleLog(bleLines, bleEl, `${err.name || 'Error'}: ${err.message || ''}`)
    bleStatus.value = 'BLE trigger failed: ' + (err.message || '')
    bleActive.value = false
  } finally {
    if (btDevice?.gatt?.connected) btDevice.gatt.disconnect()
  }
}

// ── Init ──
onMounted(() => {
  loadPrebuiltInfo()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (flashPort) {
    flashPort.close().catch(() => {})
  }
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

    <!-- Quick Flash -->
    <UCard class="mb-4">
      <template #header>
        <span class="font-semibold">Pre-Built Firmware</span>
      </template>
      <p class="text-sm text-muted mb-3">Download and flash pre-built images (mock credentials — shows error screen on boot).</p>
      <div class="flex gap-3">
        <UButton color="primary" variant="outline" block :disabled="prebuiltDisabled('e1002')" @click="quickFlash('e1002')">{{ prebuiltLabel('e1002') }}</UButton>
        <UButton color="primary" variant="outline" block :disabled="prebuiltDisabled('e1001')" @click="quickFlash('e1001')">{{ prebuiltLabel('e1001') }}</UButton>
      </div>
      <p v-if="qfStatus" class="mt-3 text-sm" :class="qfStatus === 'error' ? 'text-red-500' : qfStatus === 'done' ? 'text-green-500' : 'text-yellow-500'">
        {{ qfStatus === 'fetching' ? 'Downloading...' : qfStatus === 'done' ? 'Download ready' : 'Error' }}
      </p>
      <pre
        v-if="qfLines.length"
        ref="qfEl"
        class="console mt-2"
      >{{ qfLines.join('\n') }}</pre>
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

        <UProgress
          v-if="buildStatus === 'building' || buildStatus === 'queued'"
          animation="carousel"
          class="mt-2"
        />
        <p v-if="buildStatus === 'building'" class="text-xs text-muted mt-1">
          First build downloads toolchains — may take 2–5 min
        </p>

        <pre
          ref="buildEl"
          class="console mt-2"
          :class="{ hidden: !buildLines.length }"
        >{{ buildLines.join('\n') }}</pre>

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

    <!-- Local Firmware -->
    <UCard class="mb-4">
      <template #header>
        <span class="font-semibold">Flash Local Firmware</span>
      </template>
      <p class="text-sm text-muted mb-3">Skip the server build — flash a <code class="text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">firmware.bin</code> you already have.</p>
      <input type="file" id="local-file-input" accept=".bin" class="hidden" @change="handleLocalFile">
      <div class="flex items-center gap-3">
        <UButton color="neutral" variant="outline" @click="(document.getElementById('local-file-input') as HTMLInputElement)?.click()">
          {{ localFileName ? 'Change file' : 'Choose firmware.bin' }}
        </UButton>
        <span v-if="localFileName" class="text-sm text-green-500">{{ localFileName }} ({{ localBinSize }})</span>
        <UButton v-if="localFileName" color="neutral" variant="ghost" icon="i-lucide-x" size="sm" @click="clearLocalFile" />
      </div>
    </UCard>

    <!-- Flash to Device -->
    <UCard v-if="flashCardVisible" ref="flashCardRef" class="mb-4 border-2 border-green-500">
      <template #header>
        <span class="font-semibold text-green-500">Flash to Device</span>
      </template>
      <p class="text-sm text-muted mb-3">
        Source: {{ flashSource === 'local' ? '📁 ' + flashSourceDetail : flashSource === 'build' ? '🔨 Server build (' + flashSourceDetail + ')' : 'Ready' }}
      </p>
      <UButton
        color="primary"
        block
        :loading="flashing"
        @click="startFlash"
      >
        {{ flashing ? 'Flashing...' : 'Flash via USB' }}
      </UButton>

      <div v-if="flashing || flashStatus" class="mt-3">
        <p class="text-sm" :class="flashStatus.includes('failed') || flashStatus.includes('error') ? 'text-red-500' : flashStatus.includes('complete') ? 'text-green-500' : 'text-yellow-500'">
          {{ flashStatus }}
        </p>
        <UProgress
          v-if="flashing"
          :value="flashProgress > 0 ? flashProgress : undefined"
          :animation="flashProgress > 0 ? undefined : 'carousel'"
          class="mt-2"
        />
        <pre
          v-if="flashLines.length"
          ref="flashEl"
          class="console mt-2"
        >{{ flashLines.join('\n') }}</pre>
      </div>

      <p class="text-xs text-muted mt-3 space-y-1">
        <span class="block"><strong>①</strong> Connect reTerminal via USB-C</span>
        <span class="block"><strong>②</strong> Click <strong>Flash via USB</strong> and select the serial port</span>
        <span class="block">Auto-reset handles everything — no button presses needed.</span>
        <span class="block">If flashing fails, try: hold BOOT → press RESET → release BOOT → retry.</span>
      </p>
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
      <pre
        v-if="bleLines.length"
        ref="bleEl"
        class="console mt-2"
      >{{ bleLines.join('\n') }}</pre>
    </UCard>
  </div>
</template>

<style scoped>
.console {
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  line-height: 1.5;
  padding: 0.75rem;
  border-radius: 0.5rem;
  max-height: 20rem;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  color: #4ade80;
  background: #0f172a;
}
:root.dark .console {
  color: #86efac;
  background: #020617;
}
</style>
