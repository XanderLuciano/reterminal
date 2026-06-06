<script setup lang="ts">
import type { Screen } from '~/types'

const toast = useToast()
const screenList = ref<Screen[]>([])
const loading = ref(true)
const showForm = ref(false)
const editingId = ref<string | null>(null)

const form = ref({
  name: '',
  type: 'url' as string,
  configStr: '{}'
})
const formErrors = ref<Record<string, string>>({})

const typeOptions = ['url', 'html', 'weather', 'maintenance']

const columns = [
  { accessorKey: 'name', header: 'Name', enableSorting: true },
  { accessorKey: 'type', header: 'Type' },
  { accessorKey: 'updatedAt', header: 'Updated' },
  { accessorKey: 'actions', header: '' }
]

async function fetchScreens() {
  loading.value = true
  try {
    screenList.value = await $fetch('/api/screens') as Screen[]
  } catch (err: any) {
    toast.add({ title: 'Error', description: err.statusMessage || 'Failed to load screens', color: 'error' })
  } finally {
    loading.value = false
  }
}

function formatDate(ts: number) {
  return new Date(ts).toLocaleString()
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', type: 'url', configStr: '{\n  "url": ""\n}' }
  formErrors.value = {}
  showForm.value = true
}

function openEdit(screen: Screen) {
  editingId.value = screen.id
  form.value = {
    name: screen.name,
    type: screen.type,
    configStr: JSON.stringify(screen.config, null, 2)
  }
  formErrors.value = {}
  showForm.value = true
}

async function saveScreen() {
  formErrors.value = {}
  let config: unknown
  try {
    config = JSON.parse(form.value.configStr)
  } catch {
    formErrors.value.configStr = 'Invalid JSON'
    return
  }

  const payload = {
    name: form.value.name,
    type: form.value.type,
    config: config as Record<string, unknown>
  }

  try {
    if (editingId.value) {
      await $fetch(`/api/screens/${editingId.value}`, { method: 'PUT', body: payload })
      toast.add({ title: 'Updated', description: `Screen "${payload.name}" updated`, color: 'success' })
    } else {
      await $fetch('/api/screens', { method: 'POST', body: payload })
      toast.add({ title: 'Created', description: `Screen "${payload.name}" created`, color: 'success' })
    }
    showForm.value = false
    await fetchScreens()
  } catch (err: any) {
    if (err.data?.fieldErrors) {
      for (const [k, v] of Object.entries(err.data.fieldErrors)) {
        formErrors.value[k] = (v as string[])[0]
      }
    } else {
      toast.add({ title: 'Error', description: err.statusMessage || 'Failed to save screen', color: 'error' })
    }
  }
}

async function deleteScreen(id: string, name: string) {
  if (!confirm(`Delete screen "${name}"? This also removes it from all devices.`)) return
  try {
    await $fetch(`/api/screens/${id}`, { method: 'DELETE' })
    toast.add({ title: 'Deleted', description: `Screen "${name}" removed`, color: 'success' })
    await fetchScreens()
  } catch (err: any) {
    toast.add({ title: 'Error', description: err.statusMessage || 'Failed to delete screen', color: 'error' })
  }
}

function getTypeBadge(type: string) {
  const colors: Record<string, string> = {
    url: 'primary',
    html: 'warning',
    weather: 'info',
    maintenance: 'neutral'
  }
  return colors[type] || 'neutral'
}

onMounted(() => fetchScreens())
</script>

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold">Screens</h1>
        <p class="text-muted text-sm mt-1">Create and manage display screen templates</p>
      </div>
      <UButton icon="i-lucide-plus" @click="openCreate">New Screen</UButton>
    </div>

    <UCard>
      <UTable
        :data="screenList"
        :columns="columns"
        :loading="loading"
        empty="No screens created"
      >
        <template #empty>
          <div class="text-center py-8 text-muted">
            <UIcon name="i-lucide-monitor" class="text-3xl mb-2" />
            <p>No screens created</p>
          </div>
        </template>
      >
        <template #type-data="{ row }">
          <UBadge :color="getTypeBadge(row.type)" variant="subtle" size="sm">
            {{ row.type }}
          </UBadge>
        </template>
        <template #updatedAt-data="{ row }">
          <span class="text-sm text-muted">{{ formatDate(row.updatedAt) }}</span>
        </template>
        <template #actions-data="{ row }">
          <div class="flex gap-1 justify-end">
            <UButton
              icon="i-lucide-pencil"
              size="xs"
              variant="ghost"
              color="primary"
              @click="openEdit(row)"
            />
            <UButton
              icon="i-lucide-trash"
              size="xs"
              variant="ghost"
              color="error"
              @click="deleteScreen(row.id, row.name)"
            />
          </div>
        </template>
      </UTable>
    </UCard>

    <!-- Create/Edit Modal -->
    <UModal v-model:open="showForm" :title="editingId ? 'Edit Screen' : 'New Screen'">
      <template #body>
        <div class="space-y-4">
          <UFormField label="Name" :error="formErrors.name" required>
            <UInput v-model="form.name" placeholder="My Screen" />
          </UFormField>
          <UFormField label="Type" :error="formErrors.type" required>
            <USelect v-model="form.type" :items="typeOptions" />
          </UFormField>
          <UFormField label="Config (JSON)" :error="formErrors.configStr" required>
            <UTextarea
              v-model="form.configStr"
              :rows="8"
              placeholder='{"url": "https://..."}'
              class="font-mono text-sm"
            />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <UButton color="neutral" variant="ghost" @click="showForm = false">Cancel</UButton>
        <UButton @click="saveScreen">{{ editingId ? 'Update' : 'Create' }}</UButton>
      </template>
    </UModal>
  </div>
</template>
