import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendProxy = {
  '/api': {
    target: 'http://127.0.0.1:5000',
    changeOrigin: true,
  },
  '/uploads': {
    target: 'http://127.0.0.1:5000',
    changeOrigin: true,
  },
};

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    strictPort: true,
    proxy: { ...backendProxy },
  },
  // npm run preview 默认不带 server.proxy，会导致 /api 打到预览服务本身 → 404「请求的资源不存在」
  preview: {
    port: 4173,
    proxy: { ...backendProxy },
  },
})