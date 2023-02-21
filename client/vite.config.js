import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import inject from "@rollup/plugin-inject";

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [
      // inject({   // => that should be first under plugins array
      //   jQuery: 'jquery',
      // }),
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
        'balm-ui-plus-source': 'balm-ui/src/scripts/balm-ui-plus.js',
        // jquery: 'jquery/dist/jquery.slim.js' // this line adds the exclusion
      }
    },
    build: {
      chunkSizeWarningLimit: 1048576, // 1MB in bytes
      rollupOptions: {
        input: {
          main: 'index.html'
        },
        output: {
          entryFileNames: '[name].[hash].js',
          chunkFileNames: '[name].[hash].js',
          assetFileNames: '[name].[hash].[ext]'
        },
        plugins: [],
        external: [
          // 'jquery', // add this line to exclude jQuery from being processed by Babel
          // 'axios'
        ]
      }
    }
  }
})
