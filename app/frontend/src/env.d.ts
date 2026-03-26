/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_DEV_TELEGRAM_USER_ID?: string;
  readonly VITE_DEV_TELEGRAM_USERNAME?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
