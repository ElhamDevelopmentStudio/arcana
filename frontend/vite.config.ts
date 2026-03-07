import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import path from "path"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(),tailwindcss(),],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          const normalizedId = id.toLowerCase().replaceAll('\\', '/')
          const pageProjectsMarker = '/src/pages/projects/';
          if (normalizedId.includes('/src/pages/')) {
            if (normalizedId.includes(pageProjectsMarker)) {
              const routeFileName = normalizedId.split(pageProjectsMarker)[1]?.split('/')[0];
              if (routeFileName) {
                return `pages-projects-${routeFileName.replaceAll('.tsx', '').replaceAll('.ts', '')}`;
              }
              return 'pages-projects'
            }
            if (normalizedId.includes('/src/pages/auth/')) {
              return 'pages-auth'
            }
            return 'pages'
          }
          if (normalizedId.includes('/src/features/workflow/')) {
            return 'feature-workflow'
          }
          if (normalizedId.includes('/src/components/ui/')) {
            return 'ui-components'
          }
          if (normalizedId.includes('/src/components/')) {
            return 'components'
          }
          return undefined
        },
      },
    },
    chunkSizeWarningLimit: 500,
  },
}) 
