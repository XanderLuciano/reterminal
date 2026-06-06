<script setup lang="ts">
const config = useRuntimeConfig()
const API_BASE = config.public.apiBase

interface PageMeta {
  name: string
  url: string
  title: string
  interval_minutes: number
  selector?: string
  rendered_at?: string
  file_size?: number
}

// ── State ──
const pages = ref<PageMeta[]>([])
const loading = ref(true)
const error = ref('')
const previewName = ref('')
const previewUrl = ref('')
const saving = ref(false)

// ── Create/edit dialog ──
const showDialog = ref(false)
const editingPage = ref<PageMeta | null>(null)
const formName = ref('')
const formUrl = ref('')
const formTitle = ref('')
const formInterval = ref(30)
const formSelector = ref('')
const formError = ref('')

// ── Load pages ──
async function loadPages() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`${API_BASE}/pages`)
    const data = await res.json()
    pages.value = data.pages || []
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load pages'
  } finally {
    loading.value = false
  }
}

async function loadPageMeta(name: string) {
  try {
    const res = await fetch(`${API_BASE}/page/${name}/meta`)
    const meta = await res.json()
    // Update the page in the list with rendered metadata
    const idx = pages.value.findIndex(p => p.name === name)
    if (idx >= 0) {
      pages.value[idx] = { ...pages.value[idx], ...meta }
    }
  } catch {
    // meta not available
  }
}

// ── Preview ──
const previewOpen = computed({
  get: () => !!previewUrl.value && previewName.value !== '',
  set: (val: boolean) => { if (!val) { previewName.value = ''; previewUrl.value = '' } }
})

function previewPage(name: string) {
  previewName.value = name
  previewUrl.value = `${API_BASE}/page/${name}.png`
}

// ── Delete ──
async function deletePage(name: string) {
  if (!confirm(`Delete page "${name}"?`)) return
  try {
    const res = await fetch(`${API_BASE}/page/${name}`, { method: 'DELETE' })
    if (res.ok) {
      await loadPages()
      if (previewName.value === name) {
        previewName.value = ''
        previewUrl.value = ''
      }
    }
  } catch {
    // error handled implicitly
  }
}

// ── Re-render ──
async function rerenderPage(name: string) {
  saving.value = true
  try {
    await fetch(`${API_BASE}/page/${name}/refresh`, { method: 'POST' })
    await loadPageMeta(name)
  } catch {
    // error handled implicitly
  } finally {
    saving.value = false
  }
}

// ── Edit / Create ──
function openCreate() {
  editingPage.value = null
  formName.value = ''
  formUrl.value = ''
  formTitle.value = ''
  formInterval.value = 30
  formSelector.value = ''
  formError.value = ''
  showDialog.value = true
}

function openEdit(page: PageMeta) {
  editingPage.value = page
  formName.value = page.name
  formUrl.value = page.url
  formTitle.value = page.title
  formInterval.value = page.interval_minutes
  formSelector.value = page.selector || ''
  formError.value = ''
  showDialog.value = true
}

async function savePage() {
  formError.value = ''
  if (!formName.value || !formUrl.value) {
    formError.value = 'Name and URL are required'
    return
  }

  saving.value = true
  try {
    const body: Record<string, unknown> = {
      url: formUrl.value,
      title: formTitle.value,
      interval_minutes: formInterval.value
    }
    if (formSelector.value) body.selector = formSelector.value

    const method = editingPage.value ? 'PUT' : 'POST'
    const endpoint = editingPage.value
      ? `${API_BASE}/page/${editingPage.value.name}`
      : `${API_BASE}/page/${formName.value}`

    const res = await fetch(endpoint, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })

    if (!res.ok) {
      const err = await res.json()
      formError.value = err.error || 'Save failed'
      return
    }

    showDialog.value = false
    await loadPages()
  } catch (e: unknown) {
    formError.value = e instanceof Error ? e.message : 'Save failed'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadPages()
  for (const p of pages.value) {
    await loadPageMeta(p.name)
  }
})
</script>

<template>
  <div class="p-6 max-w-4xl">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold mb-1">Page Manager</h1>
        <p class="text-muted">Create and manage the pages displayed on your e-ink screen.</p>
      </div>
      <UButton color="primary" @click="openCreate">
        <UIcon name="i-lucide-plus" />
        New Page
      </UButton>
    </div>

    <!-- Error -->
    <UAlert v-if="error" color="error" variant="outline" :title="error" class="mb-4" />

    <!-- Page list -->
    <UCard v-if="loading" class="mb-4">
      <div class="text-center py-8 text-muted">Loading pages...</div>
    </UCard>

    <div v-else class="space-y-4">
      <UCard v-for="page in pages" :key="page.name">
        <div class="flex items-start gap-4">
          <!-- Preview thumbnail -->
          <div
            class="w-40 h-24 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden flex-shrink-0 cursor-pointer border-2 border-transparent hover:border-primary-400 transition-colors"
            @click="previewPage(page.name)"
          >
            <img
              :src="`${API_BASE}/page/${page.name}.png`"
              :alt="page.title"
              class="w-full h-full object-cover"
              loading="lazy"
            >
          </div>

          <!-- Page info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <h3 class="font-semibold truncate">{{ page.title || page.name }}</h3>
              <UBadge variant="subtle" size="xs">{{ page.name }}</UBadge>
            </div>
            <p class="text-sm text-muted truncate mb-2">{{ page.url }}</p>
            <div class="flex items-center gap-4 text-xs text-muted">
              <span>Refresh: {{ page.interval_minutes }}min</span>
              <span v-if="page.rendered_at">Rendered: {{ page.rendered_at }}</span>
              <span v-if="page.file_size">{{ (page.file_size / 1024).toFixed(0) }} KB</span>
              <span v-if="page.selector">Selector: {{ page.selector }}</span>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1 flex-shrink-0">
            <UButton
              color="neutral"
              variant="ghost"
              size="xs"
              icon="i-lucide-refresh-cw"
              :loading="saving"
              @click="rerenderPage(page.name)"
            />
            <UButton
              color="neutral"
              variant="ghost"
              size="xs"
              icon="i-lucide-pencil"
              @click="openEdit(page)"
            />
            <UButton
              color="neutral"
              variant="ghost"
              size="xs"
              icon="i-lucide-trash-2"
              @click="deletePage(page.name)"
            />
          </div>
        </div>
      </UCard>

      <UCard v-if="pages.length === 0">
        <div class="text-center py-8 text-muted">
          <UIcon name="i-lucide-inbox" class="text-3xl mb-2" />
          <p>No pages configured yet.</p>
          <UButton color="primary" variant="outline" size="sm" class="mt-3" @click="openCreate">
            Create your first page
          </UButton>
        </div>
      </UCard>
    </div>

    <!-- Full preview modal -->
    <UModal v-model:open="previewOpen" title="Page Preview" v-if="previewUrl">
      <template #body>
        <img :src="previewUrl" :alt="previewName" class="w-full max-h-96 object-contain">
      </template>
    </UModal>

    <!-- Create/Edit dialog -->
    <UModal v-model:open="showDialog" :title="editingPage ? 'Edit Page' : 'New Page'">
      <template #body>
        <div class="space-y-4">
          <UAlert v-if="formError" color="error" variant="outline" :title="formError" />

          <UFormField label="Name" required :help="'URL-safe identifier: lowercase, hyphens, no spaces'">
            <UInput
              v-model="formName"
              placeholder="weather-radar"
              :disabled="!!editingPage"
            />
          </UFormField>

          <UFormField label="URL" required :help="'The webpage to screenshot for this e-ink page'">
            <UInput v-model="formUrl" placeholder="https://example.com/radar" />
          </UFormField>

          <UFormField label="Title" help="Display name shown in the page list">
            <UInput v-model="formTitle" placeholder="Weather Radar" />
          </UFormField>

          <UFormField label="Refresh Interval (minutes)" help="How often to re-fetch this page">
            <UInput v-model.number="formInterval" type="number" :min="5" :max="1440" placeholder="30" />
          </UFormField>

          <UFormField label="CSS Selector (optional)" help="Capture only a specific element instead of full page">
            <UInput v-model="formSelector" placeholder="#radar-container" />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-3">
          <UButton color="neutral" variant="outline" @click="showDialog = false">Cancel</UButton>
          <UButton color="primary" :loading="saving" @click="savePage">
            {{ editingPage ? 'Save Changes' : 'Create Page' }}
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>
