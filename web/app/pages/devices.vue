<script setup lang="ts">
import type { Device } from '~/types'

const toast = useToast()
const devices = ref<Device[]>([])
const loading = ref(true)
const showRegister = ref(false)
const showDetail = ref(false)
const selectedDevice = ref<Device | null>(null)

const form = ref({
  id: '',
  name: 'Unnamed',
  variant: 'e1001'
})
const formErrors = ref<Record<string, string>>({})

const columns = [
  { key: 'id', label: 'ID', sortable: true },
  { key: 'name', label: 'Name', sortable: true },
  { key: 'variant', label: 'Variant' },
  { key: 'batteryPct', label: 'Battery' },
  { key: 'chargeState', label: 'Charge' },
  { key: 'screenCount', label: 'Screens' },
  { key: 'lastSeen', label: 'Last Seen' },
  { key: 'actions', label: '' }
]

async function fetchDevices() {
  loading.value = true
  try {
    const data = await $fetch('/api/devices')
    devices.value = data as Device[]
  } catch (err: any) {
    toast.add({ title: 'Error', description: err.statusMessage || 'Failed to load devices', color: 'error' })
  } finally {
    loading.value = false
  }
}

function formatLastSeen(ts: number | null) {
  if (!ts) return 'Never'
  const diff = Date.now() - ts
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatCharge(state: string | null) {
  if (!state) return '—'
  const labels: Record<string, string> = {
    battery: '🔋 Batt',
    charging: '⚡ Charging',
    full: '✅ Full'
  }
  return labels[state] || state
}

function formatBattery(pct: number | null) {
  if (pct == null || pct === -1) return '—'
  if (pct === -2) return '⚡ USB'
  return `${pct}%`
}

function openDetail(device: Device) {
  selectedDevice.value = device
  showDetail.value = true
}

async function loadDetail(id: string) {
  try {
    const data = await $fetch(`/api/devices/${id}`)
    selectedDevice.value = data as Device
  } catch (err: any) {
    toast.add({ title: 'Error', description: err.statusMessage || 'Failed to load device', color: 'error' })
  }
}

function openRegister() {
  form.value = { id: '', name: 'Unnamed', variant: 'e1001' }
  formErrors.value = {}
  showRegister.value = true
}

async function registerDevice() {
  formErrors.value = {}
  try {
    await $fetch('/api/devices', { method: 'POST', body: form.value })
    showRegister.value = false
    toast.add({ title: 'Success', description: 'Device registered', color: 'success' })
    await fetchDevices()
  } catch (err: any) {
    if (err.data?.fieldErrors) {
      for (const [k, v] of Object.entries(err.data.fieldErrors)) {
        formErrors.value[k] = (v as string[])[0]
      }
    } else {
      toast.add({ title: 'Error', description: err.statusMessage || 'Failed to register device', color: 'error' })
    }
  }
}

async function deleteDevice(id: string, name: string) {
  if (!confirm(`Delete device "${name}"?`)) return
  try {
    await $fetch(`/api/devices/${id}`, { method: 'DELETE' })
    toast.add({ title: 'Deleted', description: `Device "${name}" removed`, color: 'success' })
    await fetchDevices()
  } catch (err: any) {
    toast.add({ title: 'Error', description: err.statusMessage || 'Failed to delete device', color: 'error' })
  }
}

onMounted(() => fetchDevices())
</script>

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">Devices</h1>
        <p class="text-muted text-sm mt-1">Manage registered e-ink display devices</p>
      </div>
      <UButton icon="i-lucide-plus" @click="openRegister">Register Device</UButton>
    </div>

    <UCard>
      <UTable
        :data="devices"
        :columns="columns"
        :loading="loading"
        empty="No devices registered"
      >
        <template #empty>
          <div class="text-center py-8 text-muted">
            <UIcon name="i-lucide-tablet" class="text-3xl mb-2" />
            <p>No devices registered</p>
          </div>
        </template>
        <template #batteryPct-data="{ row }">
          <UBadge :color="(row.batteryPct ?? 0) > 20 ? 'primary' : 'error'" variant="subtle">
            {{ formatBattery(row.batteryPct) }}
          </UBadge>
        </template>
        <template #chargeState-data="{ row }">
          <span class="text-sm">{{ formatCharge(row.chargeState) }}</span>
        </template>
        <template #lastSeen-data="{ row }">
          <span class="text-sm text-muted">{{ formatLastSeen(row.lastSeen) }}</span>
        </template>
        <template #actions-data="{ row }">
          <div class="flex gap-1 justify-end">
            <UButton
              icon="i-lucide-eye"
              size="xs"
              variant="ghost"
              color="primary"
              @click="openDetail(row); loadDetail(row.id)"
            />
            <UButton
              icon="i-lucide-trash"
              size="xs"
              variant="ghost"
              color="error"
              @click="deleteDevice(row.id, row.name)"
            />
          </div>
        </template>
      </UTable>
    </UCard>

    <!-- Register Modal -->
    <UModal v-model:open="showRegister" title="Register Device">
      <template #body>
        <div class="space-y-4">
          <UFormField label="Device ID" :error="formErrors.id" required>
            <UInput v-model="form.id" placeholder="e.g., e1001-a1b2c3" />
          </UFormField>
          <UFormField label="Name" :error="formErrors.name">
            <UInput v-model="form.name" placeholder="Unnamed" />
          </UFormField>
          <UFormField label="Variant" :error="formErrors.variant" required>
            <USelect v-model="form.variant" :items="['e1001', 'e1002']" />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <UButton color="neutral" variant="ghost" @click="showRegister = false">Cancel</UButton>
        <UButton @click="registerDevice">Register</UButton>
      </template>
    </UModal>

    <!-- Detail Modal -->
    <UModal v-model:open="showDetail" :title="selectedDevice?.name || 'Device Details'">
      <template #body>
        <div v-if="selectedDevice" class="space-y-3">
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div><span class="text-muted">ID:</span> {{ selectedDevice.id }}</div>
            <div><span class="text-muted">Variant:</span> {{ selectedDevice.variant }}</div>
            <div><span class="text-muted">Battery:</span> {{ formatBattery(selectedDevice.batteryPct) }}</div>
            <div><span class="text-muted">Charge:</span> {{ formatCharge(selectedDevice.chargeState) }}</div>
            <div><span class="text-muted">Firmware:</span> {{ selectedDevice.firmwareVersion || '—' }}</div>
            <div><span class="text-muted">Last Seen:</span> {{ formatLastSeen(selectedDevice.lastSeen) }}</div>
          </div>
          <USeparator v-if="selectedDevice.assignedScreens?.length" />
          <div v-if="selectedDevice.assignedScreens?.length">
            <p class="text-sm font-medium mb-2">Assigned Screens ({{ selectedDevice.assignedScreens.length }})</p>
            <div class="space-y-2">
              <div
                v-for="(as, i) in selectedDevice.assignedScreens"
                :key="as.id"
                class="flex items-center gap-2 text-sm p-2 rounded bg-muted/50"
              >
                <span class="text-muted">{{ i + 1 }}.</span>
                <span>{{ as.name }}</span>
                <UBadge size="xs" variant="subtle">{{ as.type }}</UBadge>
                <span class="text-muted ml-auto">{{ as.refresh_interval ? as.refresh_interval + 's' : '' }}</span>
                <UBadge :color="as.enabled ? 'success' : 'neutral'" size="xs" variant="subtle">
                  {{ as.enabled ? 'On' : 'Off' }}
                </UBadge>
              </div>
            </div>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
