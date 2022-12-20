import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [vue()],
    define: {
      __APP_ENV__: env.APP_ENV,
      global: {},
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        vue: 'vue/dist/vue.esm-bundler.js',
        'balm-ui-plus': 'balm-ui/dist/balm-ui-plus.esm.js',
        'balm-ui-css': 'balm-ui/dist/balm-ui.css',
        'balm-ui-source': 'balm-ui/src/scripts/balm-ui.js',
        'balm-ui-plus-source': 'balm-ui/src/scripts/balm-ui-plus.js'
      }
    }
  }
})
