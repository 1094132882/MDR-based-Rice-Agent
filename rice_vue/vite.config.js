import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '..', '')
    return {
        plugins: [vue()],
        server: { proxy: { '/api': {
            target: process.env.BACKEND_URL || env.BACKEND_URL || 'http://127.0.0.1:11500',
            changeOrigin: true,
            rewrite: path => path.replace(/^\/api/, '')
        } } }
    }
})
