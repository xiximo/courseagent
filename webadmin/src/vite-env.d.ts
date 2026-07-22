/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEV_MOCK?: string
  readonly VITE_QIBIAO_MOCK?: string
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
