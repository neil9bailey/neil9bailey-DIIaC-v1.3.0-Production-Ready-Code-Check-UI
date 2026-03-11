/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_ENTRA_CLIENT_ID?: string;
  readonly VITE_ENTRA_TENANT_ID?: string;
  readonly VITE_ENTRA_REDIRECT_URI?: string;
  readonly VITE_ENTRA_GROUP_MAP?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
