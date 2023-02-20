import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import inject from "@rollup/plugin-inject";

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [
      inject({   // => that should be first under plugins array
        $: 'jquery',
        jQuery: 'jquery',
      }),
      vue(),
    ],
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
    },
  }
})
