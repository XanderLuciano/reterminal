// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui'
  ],

  devtools: {
    enabled: true
  },

  css: ['~/assets/css/main.css'],

  compatibilityDate: '2025-01-15',

  runtimeConfig: {
    public: {
      // Dev: http://localhost:8088 (Flask on separate port)
      // Production behind reverse proxy: empty string (same-origin)
      apiBase: process.env.API_BASE || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8088')
    }
  },

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  }
})
