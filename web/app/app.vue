<script setup lang="ts">
useHead({
  meta: [
    { name: 'viewport', content: 'width=device-width, initial-scale=1' }
  ],
  link: [
    { rel: 'icon', href: '/favicon.ico' }
  ],
  htmlAttrs: {
    lang: 'en'
  }
})

const title = 'E-Ink Dashboard'
const description = 'Web flasher & page manager for reTerminal E10xx e-paper displays.'

useSeoMeta({
  title,
  description,
  ogTitle: title,
  ogDescription: description,
})
</script>

<template>
  <UApp>
    <UDashboardGroup>
      <UDashboardSidebar>
        <template #header>
          <NuxtLink to="/" class="flex items-center gap-2 px-1">
            <span class="font-bold text-lg bg-gradient-to-r from-primary-500 to-primary-400 bg-clip-text text-transparent tracking-wide">E-Ink Dashboard</span>
          </NuxtLink>
        </template>

        <UNavigationMenu
          :items="[
            { label: 'Home', icon: 'i-lucide-home', to: '/' },
            { label: 'Devices', icon: 'i-lucide-tablet', to: '/devices' },
            { label: 'Screens', icon: 'i-lucide-monitor', to: '/screens' },
            { label: 'Assign', icon: 'i-lucide-link', to: '/device-screens' },
            { label: 'Flasher', icon: 'i-lucide-zap', to: '/flasher' },
            { label: 'Pages', icon: 'i-lucide-layout-dashboard', to: '/pages' }
          ]"
          orientation="vertical"
        />

        <template #footer>
          <div class="flex items-center justify-between px-1">
            <span class="text-xs text-muted">v1.0-beta</span>
            <UColorModeButton size="xs" />
          </div>
        </template>
      </UDashboardSidebar>

      <UDashboardPanel>
        <template #header>
          <UDashboardSidebarToggle />
        </template>
        <template #body>
          <NuxtPage />
        </template>
      </UDashboardPanel>
    </UDashboardGroup>
  </UApp>
</template>
