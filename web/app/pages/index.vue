<template>
  <div class="p-8 max-w-3xl">
    <h1 class="text-3xl font-bold mb-6">reTerminal E-Ink Dashboard</h1>

    <p class="text-lg text-muted mb-8">
      Open-source firmware, server, and web tools for Seeed Studio reTerminal
      E10xx e-paper displays. Turn your e-ink screen into a low-power, always-on
      dashboard with weather, maintenance tracking, and custom URL pages.
    </p>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-10">
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-zap" class="text-primary-500" />
            <span class="font-semibold">Web Flasher</span>
          </div>
        </template>
        <p class="text-sm text-muted mb-4">
          Configure WiFi, server URL, and sleep timings. Build and flash custom
          firmware directly from the browser — no CLI needed.
        </p>
        <UButton to="/flasher" color="primary" variant="outline" size="sm">
          Open Flasher
        </UButton>
      </UCard>

      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-layout-dashboard" class="text-primary-500" />
            <span class="font-semibold">Page Manager</span>
          </div>
        </template>
        <p class="text-sm text-muted mb-4">
          Create, edit, and organize the pages displayed on your e-ink screen.
          Configure URL screenshots, HTML templates, and page ordering.
        </p>
        <UButton to="/pages" color="primary" variant="outline" size="sm">
          Manage Pages
        </UButton>
      </UCard>
    </div>

    <h2 class="text-xl font-semibold mb-4">Supported Devices</h2>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
      <UCard>
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
            <span class="font-bold text-primary-600">E1</span>
          </div>
          <div>
            <p class="font-semibold text-sm">E1001</p>
            <p class="text-xs text-muted">7.5" Monochrome · 800×480</p>
          </div>
        </div>
      </UCard>
      <UCard>
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
            <span class="font-bold text-primary-600">E2</span>
          </div>
          <div>
            <p class="font-semibold text-sm">E1002</p>
            <p class="text-xs text-muted">7.3" Spectra 6 Color · 800×480</p>
          </div>
        </div>
      </UCard>
    </div>

    <h2 class="text-xl font-semibold mb-4">Quick Start</h2>
    <div class="space-y-3 text-sm text-muted">
      <p>1. Connect your reTerminal E10xx via USB-C</p>
      <p>2. Open the <NuxtLink to="/flasher" class="text-primary-500 hover:underline">Flasher</NuxtLink> and configure your WiFi</p>
      <p>3. Build and flash the firmware</p>
      <p>4. Set up your server (Docker or Python) with the dashboard templates</p>
      <p>5. Manage your pages from the <NuxtLink to="/pages" class="text-primary-500 hover:underline">Page Manager</NuxtLink></p>
    </div>
  </div>
</template>
