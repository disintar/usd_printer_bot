import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiBasePathRaw = env.VITE_API_URL ?? "/api";
  const apiBasePath = apiBasePathRaw.startsWith("/") && apiBasePathRaw !== "/" ? apiBasePathRaw : "/api";
  const proxyTarget = env.VITE_DEV_PROXY_TARGET ?? "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 5173,
      proxy: {
        [apiBasePath]: {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => {
            const rewritten = path.slice(apiBasePath.length);
            return rewritten === "" ? "/" : rewritten;
          }
        }
      }
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts"
    }
  };
});
