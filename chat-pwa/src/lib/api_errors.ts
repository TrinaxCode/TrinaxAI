/** Browser-safe error normalization shared by every API domain. */

export type ErrorCategory =
  | 'internet_unavailable'
  | 'external_service_unavailable'
  | 'ai_model_unavailable'
  | 'model_loading_failed'
  | 'tool_timeout'
  | 'permission_denied'
  | 'authentication_failed'
  | 'resource_exhausted'
  | 'memory_limit_reached'
  | 'gpu_unavailable'
  | 'file_not_found'
  | 'document_unreadable'
  | 'invalid_input'
  | 'unsupported_format'
  | 'network_timeout'
  | 'internal_server_error'
  | 'unknown_error';

type ErrorDefinition = {
  code: string;
  en: string;
  es: string;
  recoveryEn: string;
  recoveryEs: string;
  retryable: boolean;
};

const ERROR_DEFINITIONS: Record<ErrorCategory, ErrorDefinition> = {
  internet_unavailable: { code: 'ERR_INTERNET_UNAVAILABLE', en: 'The internet connection is unavailable.', es: 'La conexión a Internet no está disponible.', recoveryEn: 'Check the network connection and try again.', recoveryEs: 'Verifica la conexión de red e inténtalo de nuevo.', retryable: true },
  external_service_unavailable: { code: 'ERR_EXTERNAL_SERVICE_UNAVAILABLE', en: 'An external service is unavailable.', es: 'Un servicio externo no está disponible.', recoveryEn: 'Check the service status and try again shortly.', recoveryEs: 'Verifica el estado del servicio e inténtalo de nuevo en unos momentos.', retryable: true },
  ai_model_unavailable: { code: 'ERR_AI_MODEL_UNAVAILABLE', en: 'The selected AI model is unavailable.', es: 'El modelo de IA seleccionado no está disponible.', recoveryEn: 'Check that the model is installed and the AI service is running.', recoveryEs: 'Verifica que el modelo esté instalado y que el servicio de IA esté encendido.', retryable: false },
  model_loading_failed: { code: 'ERR_MODEL_LOADING_FAILED', en: 'The AI model could not be loaded.', es: 'No se pudo cargar el modelo de IA.', recoveryEn: 'Free system memory or select a smaller model, then try again.', recoveryEs: 'Libera memoria o selecciona un modelo más pequeño e inténtalo de nuevo.', retryable: true },
  tool_timeout: { code: 'ERR_TOOL_TIMEOUT', en: 'The operation took too long to finish.', es: 'La operación tardó demasiado en terminar.', recoveryEn: 'Try again with a smaller request or a narrower scope.', recoveryEs: 'Inténtalo de nuevo con una solicitud más pequeña o específica.', retryable: true },
  permission_denied: { code: 'ERR_PERMISSION_DENIED', en: 'You do not have permission to perform this action.', es: 'No tienes permiso para realizar esta acción.', recoveryEn: 'Request access or use an authorized device.', recoveryEs: 'Solicita acceso o usa un dispositivo autorizado.', retryable: false },
  authentication_failed: { code: 'ERR_AUTHENTICATION_FAILED', en: 'Authentication failed.', es: 'La autenticación falló.', recoveryEn: 'Sign in again or provide valid credentials.', recoveryEs: 'Inicia sesión de nuevo o proporciona credenciales válidas.', retryable: false },
  resource_exhausted: { code: 'ERR_RESOURCE_EXHAUSTED', en: 'The service has reached a temporary resource limit.', es: 'El servicio alcanzó un límite temporal de recursos.', recoveryEn: 'Wait a moment and try again.', recoveryEs: 'Espera un momento e inténtalo de nuevo.', retryable: true },
  memory_limit_reached: { code: 'ERR_MEMORY_LIMIT_REACHED', en: 'The operation needs more memory than is currently available.', es: 'La operación necesita más memoria de la disponible.', recoveryEn: 'Use a smaller file or model, or free system memory.', recoveryEs: 'Usa un archivo o modelo más pequeño, o libera memoria del sistema.', retryable: false },
  gpu_unavailable: { code: 'ERR_GPU_UNAVAILABLE', en: 'The requested GPU is unavailable.', es: 'La GPU solicitada no está disponible.', recoveryEn: 'Switch to CPU mode or make the GPU available, then try again.', recoveryEs: 'Cambia al modo CPU o habilita la GPU e inténtalo de nuevo.', retryable: false },
  file_not_found: { code: 'ERR_FILE_NOT_FOUND', en: 'The requested file was not found.', es: 'No se encontró el archivo solicitado.', recoveryEn: 'Check the file location and try again.', recoveryEs: 'Verifica la ubicación del archivo e inténtalo de nuevo.', retryable: false },
  document_unreadable: { code: 'ERR_DOCUMENT_UNREADABLE', en: 'The document could not be read.', es: 'No se pudo leer el documento.', recoveryEn: 'Check that the document is not damaged and try another copy.', recoveryEs: 'Verifica que el documento no esté dañado e inténtalo con otra copia.', retryable: false },
  invalid_input: { code: 'ERR_INVALID_INPUT', en: 'The request contains invalid input.', es: 'La solicitud contiene datos inválidos.', recoveryEn: 'Check the fields and try again.', recoveryEs: 'Verifica los campos e inténtalo de nuevo.', retryable: false },
  unsupported_format: { code: 'ERR_UNSUPPORTED_FORMAT', en: 'This file or format is not supported.', es: 'Este archivo o formato no es compatible.', recoveryEn: 'Use a supported format and try again.', recoveryEs: 'Usa un formato compatible e inténtalo de nuevo.', retryable: false },
  network_timeout: { code: 'ERR_NETWORK_TIMEOUT', en: 'The network request timed out.', es: 'La solicitud de red agotó el tiempo de espera.', recoveryEn: 'Check the connection and try again.', recoveryEs: 'Verifica la conexión e inténtalo de nuevo.', retryable: true },
  internal_server_error: { code: 'ERR_INTERNAL_SERVER_ERROR', en: 'TrinaxAI could not complete the request.', es: 'TrinaxAI no pudo completar la solicitud.', recoveryEn: 'Try again. If the problem continues, check the server logs.', recoveryEs: 'Inténtalo de nuevo. Si continúa, revisa los registros del servidor.', retryable: true },
  unknown_error: { code: 'ERR_UNKNOWN_ERROR', en: 'Something unexpected happened.', es: 'Ocurrió un error inesperado.', recoveryEn: 'Try again. If the problem continues, contact an administrator.', recoveryEs: 'Inténtalo de nuevo. Si continúa, contacta a un administrador.', retryable: false },
};

const LEGACY_ERROR_CATEGORIES: Record<string, ErrorCategory> = {
  connection_error: 'internet_unavailable',
  rag_unavailable: 'external_service_unavailable',
  ollama_unavailable: 'ai_model_unavailable',
  model_unavailable: 'ai_model_unavailable',
  model_loading_failed: 'model_loading_failed',
  document_unreadable: 'document_unreadable',
  invalid_response: 'internal_server_error',
  model_incompatible: 'ai_model_unavailable',
  embedding_error: 'ai_model_unavailable',
  collection_empty: 'file_not_found',
  collection_not_found: 'file_not_found',
  web_search_disabled: 'external_service_unavailable',
  provider_timeout: 'network_timeout',
  provider_unavailable: 'external_service_unavailable',
  system_start_failed: 'external_service_unavailable',
  web_search_unavailable: 'external_service_unavailable',
  invalid_credential: 'authentication_failed',
  rate_limited: 'resource_exhausted',
  timeout: 'network_timeout',
  rag_version_mismatch: 'external_service_unavailable',
  unsupported_format: 'unsupported_format',
};

function categoryFor(status: number, code = ''): ErrorCategory {
  if (code.startsWith('ERR_')) {
    const match = (Object.keys(ERROR_DEFINITIONS) as ErrorCategory[]).find((category) => ERROR_DEFINITIONS[category].code === code);
    if (match) return match;
  }
  if (LEGACY_ERROR_CATEGORIES[code]) return LEGACY_ERROR_CATEGORIES[code];
  if (status === 0) return 'internet_unavailable';
  if (status === 401) return 'authentication_failed';
  if (status === 403) return 'permission_denied';
  if (status === 408 || status === 504) return 'network_timeout';
  if (status === 413) return 'memory_limit_reached';
  if (status === 415 || status === 501) return 'unsupported_format';
  if (status === 429 || status === 507) return 'resource_exhausted';
  if (status === 400 || status === 422) return 'invalid_input';
  if (status === 502 || status === 503 || status === 424) return 'external_service_unavailable';
  if (status >= 500) return 'internal_server_error';
  return 'unknown_error';
}

const LEGACY_MESSAGES: Record<string, [string, string]> = {
  proxy_operation_not_exposed: ['Esta operación no está disponible a través de TrinaxAI.', 'This operation is not exposed through TrinaxAI.'],
  method_not_allowed: ['El método solicitado no está permitido.', 'The requested method is not allowed.'],
  invalid_request_url: ['La URL de la solicitud no es válida.', 'The request URL is invalid.'],
  network_refresh_failed: ['No se pudo actualizar la configuración de red local.', 'The local network configuration could not be refreshed.'],
  system_start_failed: ['No se pudieron iniciar los servicios de IA. Revisa los registros locales.', 'AI services could not be started. Check the local service logs.'],
  frontend_build_missing: ['No se encontró la compilación de la interfaz. Ejecuta npm run build.', 'The frontend build was not found. Run npm run build.'],
  proxy_scope_required: ['Este dispositivo no tiene el permiso necesario para usar esta función.', 'This device does not have the permission required for this feature.'],
  proxy_rate_limited: ['Se alcanzó el límite temporal de solicitudes. Espera un momento e inténtalo de nuevo.', 'The temporary request limit was reached. Wait a moment and try again.'],
  proxy_identity_unavailable: ['El gateway local no pudo verificar la conexión segura.', 'The local gateway could not verify the secure connection.'],
  proxy_queue_timeout: ['La cola de inferencia local tardó demasiado. Inténtalo de nuevo.', 'The local inference queue took too long. Try again.'],
  proxy_unavailable: ['El servicio de IA local no está disponible.', 'The local AI service is unavailable.'],
  ollama_unavailable: ['No se pudo conectar con Ollama.', 'Could not connect to Ollama.'],
  rag_unavailable: ['No se pudo conectar con el servicio RAG.', 'Could not connect to the RAG service.'],
  connection_error: ['No se pudo conectar con los servicios locales.', 'Could not connect to the local services.'],
  collection_empty: ['La colección seleccionada no contiene documentos indexados.', 'The selected collection contains no indexed documents.'],
  collection_not_found: ['No se encontró la colección seleccionada.', 'The selected collection was not found.'],
  proxy_invalid_configuration: ['La configuración del proxy local no es válida.', 'The local proxy configuration is invalid.'],
  system_scope_required: ['El control del sistema solo está disponible desde localhost en el equipo principal.', 'System control is available only from localhost on the host.'],
  unknown_system_action: ['La acción del sistema no es válida.', 'The system action is invalid.'],
  route_not_found: ['La ruta solicitada no existe.', 'The requested route does not exist.'],
  provider_not_configured: ['El proveedor seleccionado no está configurado.', 'The selected provider is not configured.'],
  invalid_credential: ['La credencial del proveedor no es válida.', 'The provider credential is invalid.'],
  rate_limited: ['El proveedor limitó temporalmente las solicitudes.', 'The provider temporarily rate-limited requests.'],
  provider_timeout: ['El proveedor agotó el tiempo de espera.', 'The provider timed out.'],
  provider_unavailable: ['El proveedor no está disponible o la red falló.', 'The provider is unavailable or the network failed.'],
  invalid_provider_response: ['El proveedor devolvió una respuesta inválida.', 'The provider returned an invalid response.'],
  invalid_searxng_url: ['La URL de SearXNG no es válida o no es pública.', 'The SearXNG URL is invalid or not public.'],
  externally_managed: ['Este valor está administrado por una variable de entorno.', 'This value is managed by an environment variable.'],
  model_unavailable: ['El modelo necesario no está instalado. Instálalo desde Configuración.', 'The required model is not installed. Install it from Settings.'],
  model_incompatible: ['Ningún modelo instalado es compatible con esta función.', 'No installed model is compatible with this feature.'],
  web_search_unavailable: ['El proveedor de búsqueda no está disponible. Inténtalo de nuevo pronto.', 'The search provider is unavailable. Please try again shortly.'],
  rag_version_mismatch: ['Reinicia TrinaxAI para cargar el servicio actualizado.', 'Restart TrinaxAI to load the updated service.'],
};

export function isCollectionEmptyMessage(value: unknown): boolean {
  const message = String(value || '').trim().toLowerCase();
  return LEGACY_MESSAGES.collection_empty.some((candidate) => candidate.toLowerCase() === message);
}

const LEGACY_RECOVERIES: Record<string, [string, string]> = {
  proxy_unavailable: [
    'Pulsa «Encender IA» para iniciar los servicios locales y vuelve a intentarlo.',
    'Select «Start AI» to start the local services, then try again.',
  ],
  ollama_unavailable: [
    'Pulsa «Encender IA» para iniciar los servicios locales y vuelve a intentarlo.',
    'Select «Start AI» to start the local services, then try again.',
  ],
  rag_unavailable: [
    'Pulsa «Encender IA» para iniciar los servicios locales y vuelve a intentarlo.',
    'Select «Start AI» to start the local services, then try again.',
  ],
  connection_error: [
    'Comprueba la conexión local y pulsa «Encender IA» si los servicios están apagados.',
    'Check the local connection and select «Start AI» if the services are stopped.',
  ],
  collection_empty: [
    'Abre «Indexación» para elegir una carpeta y crear documentos RAG.',
    'Open «Indexing» to choose a folder and create RAG documents.',
  ],
  collection_not_found: [
    'Abre «Indexación» para seleccionar o crear una colección válida.',
    'Open «Indexing» to select or create a valid collection.',
  ],
  system_start_failed: [
    'Verifica que TrinaxAI esté instalado correctamente y vuelve a intentarlo.',
    'Check that TrinaxAI is installed correctly, then try again.',
  ],
};

const LOCAL_AI_UNAVAILABLE_CODES = new Set([
  'proxy_unavailable',
  'ollama_unavailable',
  'rag_unavailable',
  'connection_error',
]);

function languageIsEnglish(): boolean {
  try {
    const stored = localStorage.getItem('tc-lang');
    if (stored === 'es') return false;
    if (stored === 'en') return true;
  } catch { /* storage unavailable */ }
  return typeof document !== 'undefined' && document.documentElement.lang.toLowerCase().startsWith('en');
}

function publicMessage(category: ErrorCategory, code: string, fallbackCode = ''): string {
  const legacy = LEGACY_MESSAGES[code] || LEGACY_MESSAGES[fallbackCode];
  if (legacy) return legacy[languageIsEnglish() ? 1 : 0];
  const definition = ERROR_DEFINITIONS[category];
  return languageIsEnglish() ? definition.en : definition.es;
}

function parseErrorPayload(payload: unknown): { category?: ErrorCategory; code?: string; legacyCode?: string; recovery?: string; retryable?: boolean; requestId?: string } {
  if (!payload || typeof payload !== 'object') return {};
  const root = payload as Record<string, unknown>;
  const error = root.error && typeof root.error === 'object' ? root.error as Record<string, unknown> : undefined;
  const detail = root.detail && typeof root.detail === 'object' ? root.detail as Record<string, unknown> : undefined;
  const category = (error?.category || detail?.category) as ErrorCategory | undefined;
  const canonicalCode = typeof error?.code === 'string' ? error.code : typeof detail?.error_code === 'string' ? detail.error_code : undefined;
  const legacyCode = typeof detail?.legacy_code === 'string' ? detail.legacy_code : typeof detail?.code === 'string' && !detail.code.startsWith('ERR_') ? detail.code : undefined;
  return {
    category: category && category in ERROR_DEFINITIONS ? category : undefined,
    code: canonicalCode,
    legacyCode,
    recovery: typeof error?.recovery === 'string' ? error.recovery : typeof detail?.recovery === 'string' ? detail.recovery : undefined,
    retryable: typeof error?.retryable === 'boolean' ? error.retryable : typeof detail?.retryable === 'boolean' ? detail.retryable : undefined,
    requestId: typeof root.request_id === 'string' ? root.request_id : undefined,
  };
}

/** Normalized error object used by every browser-facing API path. */
export class ApiError extends Error {
  status: number;
  code?: string;
  category: ErrorCategory;
  errorCode: string;
  recovery: string;
  retryable: boolean;
  requestId?: string;
  technicalMessage: string;
  constructor(message: string, status: number, code?: string, metadata: { category?: ErrorCategory; recovery?: string; retryable?: boolean; requestId?: string; legacyCode?: string } = {}) {
    const category = metadata.category || categoryFor(status, code);
    const definition = ERROR_DEFINITIONS[category];
    const publicText = publicMessage(category, code || '', metadata.legacyCode || '');
    super(publicText);
    this.name = 'ApiError';
    this.status = status;
    this.code = metadata.legacyCode || code;
    this.category = category;
    this.errorCode = definition.code;
    const legacyRecovery = LEGACY_RECOVERIES[metadata.legacyCode || code || ''];
    this.recovery = metadata.recovery
      || (legacyRecovery ? legacyRecovery[languageIsEnglish() ? 1 : 0] : undefined)
      || (languageIsEnglish() ? definition.recoveryEn : definition.recoveryEs);
    this.retryable = metadata.retryable ?? definition.retryable;
    this.requestId = metadata.requestId;
    this.technicalMessage = message;
    if (message !== publicText) console.error('[TrinaxAI API] request failed', { status, category, code: definition.code });
  }
}

export function apiErrorFromPayload(status: number, payload: unknown, fallbackCode = ''): ApiError {
  const parsed = typeof payload === 'string' ? (() => {
    try { return JSON.parse(payload) as unknown; } catch { return null; }
  })() : payload;
  const info = parseErrorPayload(parsed);
  const legacyCode = info.legacyCode || fallbackCode || undefined;
  return new ApiError('', status, legacyCode || info.code, {
    category: info.category || categoryFor(status, legacyCode || info.code),
    recovery: info.recovery,
    retryable: info.retryable,
    requestId: info.requestId,
    legacyCode,
  });
}

export interface UserFacingErrorDetails {
  message: string;
  recovery: string;
  retryable: boolean;
  canStartLocalAi: boolean;
  canOpenIndexing: boolean;
  canOpenSettings: boolean;
}

export function userFacingErrorDetails(error: unknown, fallbackCategory: ErrorCategory = 'unknown_error'): UserFacingErrorDetails {
  if (error instanceof ApiError) {
    return {
      message: error.message,
      recovery: error.recovery,
      retryable: error.retryable,
      canStartLocalAi: LOCAL_AI_UNAVAILABLE_CODES.has(error.code || ''),
      canOpenIndexing: error.code === 'collection_empty' || error.code === 'collection_not_found',
      canOpenSettings: error.category === 'ai_model_unavailable' || error.code === 'model_loading_failed',
    };
  }
  if (error instanceof DOMException && error.name === 'AbortError') {
    return {
      message: languageIsEnglish() ? 'This request was cancelled.' : 'Cancelaste esta petición.',
      recovery: languageIsEnglish() ? 'You can send the request again when ready.' : 'Puedes enviar la petición de nuevo cuando quieras.',
      retryable: true,
      canStartLocalAi: false,
      canOpenIndexing: false,
      canOpenSettings: false,
    };
  }
  const info = ERROR_DEFINITIONS[fallbackCategory];
  return {
    message: languageIsEnglish() ? info.en : info.es,
    recovery: languageIsEnglish() ? info.recoveryEn : info.recoveryEs,
    retryable: info.retryable,
    canStartLocalAi: false,
    canOpenIndexing: false,
    canOpenSettings: false,
  };
}

export function userFacingError(error: unknown, fallbackCategory: ErrorCategory = 'unknown_error'): string {
  return userFacingErrorDetails(error, fallbackCategory).message;
}

export function formatUserFacingError(error: unknown, fallbackCategory: ErrorCategory = 'unknown_error'): string {
  const details = userFacingErrorDetails(error, fallbackCategory);
  return `${details.message}\n\n${details.recovery}`;
}
