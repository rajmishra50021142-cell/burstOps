import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const gatewayTarget = process.env.VITE_GATEWAY_URL || 'http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com';
const cpuSimTarget = process.env.VITE_CPUSIM_URL || 'http://localhost:8002';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/gateway': {
        target: gatewayTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/gateway/, ''),
      },
      '/cpu-sim': {
        target: cpuSimTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/cpu-sim/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
