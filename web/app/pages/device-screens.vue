<script setup lang="ts">
import type { Device, Screen, DeviceScreenAssignment } from '~/types'

const toast = useToast()
const route = useRoute()

const devices = ref<Device[]>([])
const screens = ref<Screen[]>([])
const selectedDeviceId = ref<string>(route.query.device as string || '')
const assignments = ref<DeviceScreenAssignment[]>([])
const loading = ref(true)

// Assignment form
const assignmentRows = ref<Array<{
  screenId: string
  sortOrder: number
  enabled: boolean
  refreshInterval: number
}>>([])

async function fetchDevices() {
  try {
    devices.value = await $fetch('/api/devices') as Device[]
  } catch (err: any) {
    toast.add({ title: 'Error', description: 'Failed to load devices', color: 'error' })
  }
}

async function fetchScreens() {
  try {
    screens.value = await $fetch('/api/screens') as Screen[]
  } catch (err: any) {
    toast.add({ title: 'Error', description: 'Failed to load screens', color: 'error' })
  }
}

async function fetchAssignments() {
  if (!selectedDeviceId.value) {
    assignments.value = []
    return
  }
  loading.value = true
  try {
    assignments.value = await $fetch(`/api/devices/${selectedDeviceId.value}/screens`) as DeviceScreenAssignment[]
    // Populate form from current assignments
    assignmentRows.value = assignments.value.map(a => ({
      screenId: a.screenId,
      sortOrder: a.sortOrder,
      enabled: a.enabled,
      refreshInterval: a.refreshInterval
    }))
  } catch (err: any) {
    toast.add({ title: 'Error', description: err.statusMessage || 'Failed to load assignments', color: 'error' })
  } finally {
    loading.value = false
  }
}

function onDeviceChange() {
  fetchAssignments()
}

function getScreenName(screenId: string) {
  return screens.value.find(s => s.id === screenId)?.name || screenId
}

function getScreenType(screenId: string) {
  return screens.value.find(s => s.id === screenId)?.type || 'unknown'
}

function addRow() {
  assignmentRows.value.push({
    screenId: '',
    sortOrder: assignmentRows.value.length,
    enabled: true,
    refreshInterval: 6
  })
}

function removeRow(index: number) {
  assignmentRows.value.splice(index, 1)
}

function moveRow(index: number, direction: -1 | 1) {
  const newIndex = index + direction
  if (newIndex < 0 || newIndex >= assignmentRows.value.length) return
  const tmp = assignmentRows.value[index]
  assignmentRows.value[index] = assignmentRows.value[newIndex]
  assignmentRows.value[newIndex] = tmp
  // Re-number sort orders
  assignmentRows.value.forEach((r, i) => { r.sortOrder = i })
}

async function saveAssignments() {
  if (!selectedDeviceId.value) {
    toast.add({ title: 'Error', description: 'Select a device first', color: 'error' })
    return
  }

  const invalid = assignmentRows.value.some(r => !r.screenId)
  if (invalid) {
    toast.add({ title: 'Error', description: 'All rows must have a screen selected', color: 'error' })
    return
  }

  try {
    await $fetch(`/api/devices/${selectedDeviceId.value}/screens`, {
      method: 'POST',
      body: { screens: assignmentRows.value }
    })
    toast.add({ title: 'Saved', description: 'Screen assignments updated', color: 'success' })
    await fetchAssignments()
  } catch (err: any) {
    toast.add({ title: 'Error', description: err.statusMessage || 'Failed to save assignments', color: 'error' })
  }
}

onMounted(async () => {
  await Promise.all([fetchDevices(), fetchScreens()])
  if (selectedDeviceId.value) {
    await fetchAssignments()
  }
})
</script>

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">Device Screens</h1>
        <p class="text-muted text-sm mt-1">Assign and order screens for each device</p>
      </div>
    </div>

    <UCard class="mb-6">
      <div class="flex items-center gap-4">
        <UFormField label="Select Device">
          <USelect
            v-model="selectedDeviceId"
            :items="devices.map(d => ({ label: `${d.name} (${d.id})`, value: d.id }))"
            placeholder="Choose a device..."
            @update:model-value="onDeviceChange"
          />
        </UFormField>
        <span v-if="assignments.length" class="text-sm text-muted mt-5">
          {{ assignments.length }} screen{{ assignments.length !== 1 ? 's' : '' }} assigned
        </span>
      </div>
    </UCard>

    <div v-if="!selectedDeviceId" class="text-center text-muted py-12">
      <UIcon name="i-lucide-arrow-up" class="text-4xl mb-2" />
      <p>Select a device above to manage its screens</p>
    </div>

    <template v-else>
      <UCard :ui="{ body: 'p-0' }">
        <div v-if="assignmentRows.length === 0 && !loading" class="p-8 text-center text-muted">
          <p class="mb-3">No screens assigned to this device</p>
          <UButton variant="outline" icon="i-lucide-plus" @click="addRow">Add Screen</UButton>
        </div>

        <div v-else class="p-4 space-y-3">
          <div
            v-for="(row, i) in assignmentRows"
            :key="i"
            class="flex items-center gap-3 p-3 rounded-lg bg-muted/30"
          >
            <div class="flex flex-col gap-1">
              <UButton
                icon="i-lucide-chevron-up"
                size="xs"
                variant="ghost"
                :disabled="i === 0"
                @click="moveRow(i, -1)"
              />
              <UButton
                icon="i-lucide-chevron-down"
                size="xs"
                variant="ghost"
                :disabled="i === assignmentRows.length - 1"
                @click="moveRow(i, 1)"
              />
            </div>

            <span class="text-xs text-muted w-6 text-center font-mono">{{ i }}</span>

            <USelect
              v-model="row.screenId"
              :items="screens.map(s => ({ label: `${s.name} [${s.type}]`, value: s.id }))"
              placeholder="Select screen"
              class="flex-1"
            />

            <UFormField label="Refresh (hours)" class="w-28">
              <UInput v-model.number="row.refreshInterval" type="number" min="1" max="24" />
            </UFormField>

            <UCheckbox v-model="row.enabled" label="Active" />

            <UButton
              icon="i-lucide-trash"
              size="xs"
              variant="ghost"
              color="error"
              @click="removeRow(i)"
            />
          </div>

          <div class="flex gap-2 pt-2">
            <UButton variant="outline" icon="i-lucide-plus" @click="addRow">Add Screen</UButton>
            <UButton @click="saveAssignments" :disabled="assignmentRows.length === 0">Save Assignments</UButton>
          </div>
        </div>
      </UCard>

      <UCard v-if="assignments.length > 0" class="mt-6">
        <template #header>
          <h2 class="text-lg font-semibold">Firmware Preview URLs</h2>
        </template>
        <div class="space-y-2">
          <div v-for="(_, i) in assignments" :key="i" class="flex items-center gap-3 text-sm">
            <span class="text-muted font-mono">Page {{ i }}:</span>
            <code class="text-xs bg-muted px-2 py-0.5 rounded">
              /api/device/{{ selectedDeviceId }}/page/{{ i }}
            </code>
            <span class="text-muted">→ {{ assignments[i]?.screen?.name }}</span>
          </div>
        </div>
      </UCard>
    </template>
  </div>
</template>
