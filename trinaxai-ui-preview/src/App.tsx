import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import {
  IconActivity,
  IconAlert,
  IconArrowUp,
  IconBook,
  IconBot,
  IconCheck,
  IconChevronDown,
  IconChevronRight,
  IconClock,
  IconCode,
  IconCommand,
  IconDatabase,
  IconExternal,
  IconFile,
  IconFolder,
  IconGlobe,
  IconGrid,
  IconLock,
  IconMenu,
  IconMessage,
  IconMic,
  IconMoon,
  IconMore,
  IconPaperclip,
  IconPanel,
  IconPlay,
  IconPlus,
  IconRotate,
  IconSearch,
  IconServer,
  IconSettings,
  IconShield,
  IconSliders,
  IconSpark,
  IconSun,
  IconX,
} from './icons';

type View = 'chat' | 'knowledge' | 'agent' | 'indexing' | 'settings';
type Locale = 'es' | 'en';
type Theme = 'dark' | 'light';
type SettingsSection = 'general' | 'models' | 'knowledge' | 'network' | 'privacy';
type AgentDecision = 'pending' | 'approved' | 'rejected';
type IndexingState = 'running' | 'completed' | 'failed';

type TranslationKey =
  | 'brandSubtitle'
  | 'localPrivate'
  | 'navWorkspace'
  | 'navKnowledge'
  | 'navAgent'
  | 'navIndexing'
  | 'navSettings'
  | 'recent'
  | 'newChat'
  | 'searchChats'
  | 'today'
  | 'yesterday'
  | 'workspace'
  | 'workspaceHeadline'
  | 'workspaceSub'
  | 'knowledgeMode'
  | 'chatMode'
  | 'localReady'
  | 'context'
  | 'hideContext'
  | 'showContext'
  | 'model'
  | 'sources'
  | 'localKnowledge'
  | 'collection'
  | 'page'
  | 'confidence'
  | 'openKnowledge'
  | 'assistantLabel'
  | 'responseIntro'
  | 'responseBody'
  | 'composerPlaceholder'
  | 'composerHint'
  | 'send'
  | 'attach'
  | 'voice'
  | 'knowledgeTitle'
  | 'knowledgeSub'
  | 'collections'
  | 'documents'
  | 'chunks'
  | 'searchKnowledge'
  | 'allSources'
  | 'openChunk'
  | 'agentTitle'
  | 'agentSub'
  | 'workspacePath'
  | 'modelLabel'
  | 'normal'
  | 'yolo'
  | 'yoloTitle'
  | 'yoloBody'
  | 'enableYolo'
  | 'cancel'
  | 'activity'
  | 'planning'
  | 'reading'
  | 'approvalPending'
  | 'approvalTitle'
  | 'approve'
  | 'reject'
  | 'fileChange'
  | 'impact'
  | 'safeWorkspace'
  | 'indexTitle'
  | 'indexSub'
  | 'activeJob'
  | 'embedding'
  | 'files'
  | 'chunksGenerated'
  | 'elapsed'
  | 'recentActivity'
  | 'cancelJob'
  | 'retryJob'
  | 'indexingDone'
  | 'contextTitle'
  | 'activeContext'
  | 'memory'
  | 'permissions'
  | 'pairedDevice'
  | 'deviceScope'
  | 'hostLocal'
  | 'online'
  | 'fastapi'
  | 'ollama'
  | 'indexStatus'
  | 'webSearch'
  | 'voiceStatus'
  | 'ready'
  | 'connected'
  | 'synced'
  | 'available'
  | 'disabled'
  | 'theme'
  | 'language'
  | 'switchTheme'
  | 'switchLanguage'
  | 'settingsSoon'
  | 'approvalApproved'
  | 'approvalRejected'
  | 'jobCancelled'
  | 'jobRetried'
  | 'messageSent'
  | 'fileCount'
  | 'sourceCount'
  | 'previewMode'
  | 'simulatedData'
  | 'backToWorkspace'
  | 'viewDetails'
  | 'settingsTitle'
  | 'settingsSub'
  | 'settingsGeneral'
  | 'settingsModels'
  | 'settingsKnowledge'
  | 'settingsNetwork'
  | 'settingsPrivacy'
  | 'settingsAppearance'
  | 'settingsAppearanceSub'
  | 'settingsTheme'
  | 'settingsLanguage'
  | 'settingsSound'
  | 'settingsSoundSub'
  | 'settingsRuntime'
  | 'settingsRuntimeSub'
  | 'settingsActiveModel'
  | 'settingsModelSub'
  | 'settingsHardware'
  | 'settingsHardwareValue'
  | 'settingsKnowledgeTitle'
  | 'settingsKnowledgeSub'
  | 'settingsDefaultCollection'
  | 'settingsCollectionSub'
  | 'settingsAutoIndex'
  | 'settingsAutoIndexSub'
  | 'settingsNetworkTitle'
  | 'settingsNetworkSub'
  | 'settingsGateway'
  | 'settingsGatewaySub'
  | 'settingsPairing'
  | 'settingsPairingSub'
  | 'settingsPrivacyTitle'
  | 'settingsPrivacySub'
  | 'settingsInference'
  | 'settingsInferenceSub'
  | 'settingsTelemetry'
  | 'settingsTelemetrySub'
  | 'settingsSaved'
  | 'saveChanges'
  | 'settingsLocal'
  | 'settingsProtected'
  | 'settingsSelect'
  | 'settingsEnabled'
  | 'settingsDisabled'
  | 'status';

const translations: Record<Locale, Record<TranslationKey, string>> = {
  es: {
    brandSubtitle: 'Local intelligence workspace',
    localPrivate: 'Local · Privado',
    navWorkspace: 'Workspace',
    navKnowledge: 'Knowledge',
    navAgent: 'Agent',
    navIndexing: 'Indexing',
    navSettings: 'Ajustes',
    recent: 'Recientes',
    newChat: 'Nuevo chat',
    searchChats: 'Buscar chats…',
    today: 'Hoy',
    yesterday: 'Ayer',
    workspace: 'Workspace',
    workspaceHeadline: '¿En qué trabajamos?',
    workspaceSub: 'Tu contexto local está listo. Pregunta, explora o deja que TrinaxAI actúe.',
    knowledgeMode: 'Knowledge',
    chatMode: 'Chat',
    localReady: 'Local · Ready',
    context: 'Contexto',
    hideContext: 'Ocultar contexto',
    showContext: 'Mostrar contexto',
    model: 'Modelo',
    sources: 'Fuentes',
    localKnowledge: 'Conocimiento local',
    collection: 'Colección',
    page: 'Página',
    confidence: 'Confianza',
    openKnowledge: 'Abrir en Knowledge',
    assistantLabel: 'TrinaxAI · Knowledge',
    responseIntro: 'He encontrado evidencia local relevante en tu colección de producto.',
    responseBody: 'La arquitectura actual separa el gateway de la API privada y mantiene Ollama en loopback. Esto permite exponer la experiencia a la red local sin convertir el runtime de inferencia en un proxy público.',
    composerPlaceholder: 'Pregunta a tu workspace…',
    composerHint: 'Enter para enviar · Shift + Enter para nueva línea',
    send: 'Enviar',
    attach: 'Adjuntar archivo',
    voice: 'Activar voz',
    knowledgeTitle: 'Knowledge browser',
    knowledgeSub: 'Explora la evidencia que sostiene las respuestas de TrinaxAI.',
    collections: 'Colecciones',
    documents: 'Documentos',
    chunks: 'Chunks',
    searchKnowledge: 'Buscar en conocimiento…',
    allSources: 'Todas las fuentes',
    openChunk: 'Abrir chunk',
    agentTitle: 'Agent workspace',
    agentSub: 'Diseña, revisa y aprueba acciones dentro de un workspace seguro.',
    workspacePath: 'Workspace seleccionado',
    modelLabel: 'Modelo activo',
    normal: 'Normal',
    yolo: 'YOLO',
    yoloTitle: 'YOLO omite aprobaciones',
    yoloBody: 'Actívalo solo si aceptas que el agente pueda ejecutar acciones peligrosas sin pedir confirmación.',
    enableYolo: 'Activar YOLO',
    cancel: 'Cancelar',
    activity: 'Actividad',
    planning: 'Planificando la tarea',
    reading: 'Leyendo el workspace',
    approvalPending: 'Aprobación requerida',
    approvalTitle: 'El agente quiere editar un archivo',
    approve: 'Aprobar cambio',
    reject: 'Rechazar',
    fileChange: 'Cambio propuesto',
    impact: 'Impacto',
    safeWorkspace: 'Workspace aislado · Sin red',
    indexTitle: 'Indexing control room',
    indexSub: 'Sigue los trabajos de indexación sin perder el contexto del sistema.',
    activeJob: 'Trabajo activo',
    embedding: 'Generando embeddings',
    files: 'Archivos',
    chunksGenerated: 'Chunks generados',
    elapsed: 'Tiempo transcurrido',
    recentActivity: 'Actividad reciente',
    cancelJob: 'Cancelar trabajo',
    retryJob: 'Reintentar trabajo',
    indexingDone: 'Indexación completada',
    contextTitle: 'Context panel',
    activeContext: 'Contexto activo',
    memory: 'Memoria relevante',
    permissions: 'Permisos',
    pairedDevice: 'Dispositivo emparejado',
    deviceScope: 'Scopes: chat · read_private · web',
    hostLocal: 'Host local',
    online: 'Online',
    fastapi: 'FastAPI',
    ollama: 'Ollama',
    indexStatus: 'Índice',
    webSearch: 'Web search',
    voiceStatus: 'Voz',
    ready: 'Listo',
    connected: 'Conectado',
    synced: 'Sincronizado',
    available: 'Disponible',
    disabled: 'Desactivada',
    theme: 'Tema',
    language: 'Idioma',
    switchTheme: 'Cambiar tema',
    switchLanguage: 'Cambiar idioma',
    settingsSoon: 'La vista de ajustes se añadirá en el siguiente pase.',
    approvalApproved: 'Cambio aprobado. El agente puede continuar.',
    approvalRejected: 'Cambio rechazado. La sesión quedó en pausa.',
    jobCancelled: 'Trabajo cancelado de forma segura.',
    jobRetried: 'Trabajo reintentado desde la última fase estable.',
    messageSent: 'Respuesta simulada añadida al hilo.',
    fileCount: '1.248 archivos',
    sourceCount: '2 fuentes locales',
    previewMode: 'Preview mode',
    simulatedData: 'Datos simulados · Sin conexión al backend',
    backToWorkspace: 'Volver al workspace',
    viewDetails: 'Ver detalles',
    settingsTitle: 'Ajustes del sistema',
    settingsSub: 'Configura la experiencia local, los modelos y los límites de confianza de TrinaxAI.',
    settingsGeneral: 'General',
    settingsModels: 'Modelos',
    settingsKnowledge: 'Knowledge',
    settingsNetwork: 'Red y pairing',
    settingsPrivacy: 'Privacidad',
    settingsAppearance: 'Apariencia y experiencia',
    settingsAppearanceSub: 'Personaliza cómo se presenta tu workspace local.',
    settingsTheme: 'Tema de interfaz',
    settingsLanguage: 'Idioma de la interfaz',
    settingsSound: 'Sonidos de actividad',
    settingsSoundSub: 'Reproduce una señal mientras TrinaxAI está trabajando.',
    settingsRuntime: 'Runtime local',
    settingsRuntimeSub: 'Este prototipo representa un host local administrado por ti.',
    settingsActiveModel: 'Modelo de chat activo',
    settingsModelSub: 'Se reutiliza cuando el modelo ya está cargado en Ollama.',
    settingsHardware: 'Perfil de hardware',
    settingsHardwareValue: '16 GB · GPU local detectada',
    settingsKnowledgeTitle: 'Fuentes y recuperación',
    settingsKnowledgeSub: 'Decide qué conocimiento acompaña las respuestas automáticas.',
    settingsDefaultCollection: 'Colección por defecto',
    settingsCollectionSub: 'Se usará cuando el modo Knowledge no especifique otra colección.',
    settingsAutoIndex: 'Indexación automática',
    settingsAutoIndexSub: 'Detecta documentos nuevos en las carpetas observadas.',
    settingsNetworkTitle: 'Gateway y dispositivos',
    settingsNetworkSub: 'Controla cómo otros dispositivos llegan a este host local.',
    settingsGateway: 'Gateway PWA',
    settingsGatewaySub: 'Solo el gateway se expone a la red local.',
    settingsPairing: 'Pairing de dispositivos',
    settingsPairingSub: 'Los dispositivos remotos reciben scopes explícitos y revocables.',
    settingsPrivacyTitle: 'Privacidad y confianza',
    settingsPrivacySub: 'TrinaxAI mantiene los datos y la inferencia cerca de tu máquina.',
    settingsInference: 'Inferencia local',
    settingsInferenceSub: 'Las respuestas se procesan mediante Ollama en este host.',
    settingsTelemetry: 'Telemetría de producto',
    settingsTelemetrySub: 'No se envían eventos de uso en esta configuración.',
    settingsSaved: 'Ajustes guardados en esta preview.',
    saveChanges: 'Guardar cambios',
    settingsLocal: 'Local',
    settingsProtected: 'Protegido',
    settingsSelect: 'Seleccionar',
    settingsEnabled: 'Activado',
    settingsDisabled: 'Desactivado',
    status: 'Estado',
  },
  en: {
    brandSubtitle: 'Local intelligence workspace',
    localPrivate: 'Local · Private',
    navWorkspace: 'Workspace',
    navKnowledge: 'Knowledge',
    navAgent: 'Agent',
    navIndexing: 'Indexing',
    navSettings: 'Settings',
    recent: 'Recent',
    newChat: 'New chat',
    searchChats: 'Search chats…',
    today: 'Today',
    yesterday: 'Yesterday',
    workspace: 'Workspace',
    workspaceHeadline: 'What are we working on?',
    workspaceSub: 'Your local context is ready. Ask, explore, or let TrinaxAI take action.',
    knowledgeMode: 'Knowledge',
    chatMode: 'Chat',
    localReady: 'Local · Ready',
    context: 'Context',
    hideContext: 'Hide context',
    showContext: 'Show context',
    model: 'Model',
    sources: 'Sources',
    localKnowledge: 'Local knowledge',
    collection: 'Collection',
    page: 'Page',
    confidence: 'Confidence',
    openKnowledge: 'Open in Knowledge',
    assistantLabel: 'TrinaxAI · Knowledge',
    responseIntro: 'I found relevant local evidence in your product collection.',
    responseBody: 'The current architecture separates the gateway from the private API and keeps Ollama on loopback. This exposes the local-network experience without turning the inference runtime into a public proxy.',
    composerPlaceholder: 'Ask your workspace…',
    composerHint: 'Enter to send · Shift + Enter for a new line',
    send: 'Send',
    attach: 'Attach file',
    voice: 'Enable voice',
    knowledgeTitle: 'Knowledge browser',
    knowledgeSub: 'Explore the evidence behind TrinaxAI responses.',
    collections: 'Collections',
    documents: 'Documents',
    chunks: 'Chunks',
    searchKnowledge: 'Search knowledge…',
    allSources: 'All sources',
    openChunk: 'Open chunk',
    agentTitle: 'Agent workspace',
    agentSub: 'Design, review, and approve actions inside a safe workspace.',
    workspacePath: 'Selected workspace',
    modelLabel: 'Active model',
    normal: 'Normal',
    yolo: 'YOLO',
    yoloTitle: 'YOLO skips approvals',
    yoloBody: 'Enable it only if you accept that the agent may execute dangerous actions without confirmation.',
    enableYolo: 'Enable YOLO',
    cancel: 'Cancel',
    activity: 'Activity',
    planning: 'Planning the task',
    reading: 'Reading the workspace',
    approvalPending: 'Approval required',
    approvalTitle: 'The agent wants to edit a file',
    approve: 'Approve change',
    reject: 'Reject',
    fileChange: 'Proposed change',
    impact: 'Impact',
    safeWorkspace: 'Isolated workspace · No network',
    indexTitle: 'Indexing control room',
    indexSub: 'Track indexing jobs without losing system context.',
    activeJob: 'Active job',
    embedding: 'Generating embeddings',
    files: 'Files',
    chunksGenerated: 'Chunks generated',
    elapsed: 'Elapsed time',
    recentActivity: 'Recent activity',
    cancelJob: 'Cancel job',
    retryJob: 'Retry job',
    indexingDone: 'Indexing complete',
    contextTitle: 'Context panel',
    activeContext: 'Active context',
    memory: 'Relevant memory',
    permissions: 'Permissions',
    pairedDevice: 'Paired device',
    deviceScope: 'Scopes: chat · read_private · web',
    hostLocal: 'Local host',
    online: 'Online',
    fastapi: 'FastAPI',
    ollama: 'Ollama',
    indexStatus: 'Index',
    webSearch: 'Web search',
    voiceStatus: 'Voice',
    ready: 'Ready',
    connected: 'Connected',
    synced: 'Synced',
    available: 'Available',
    disabled: 'Disabled',
    theme: 'Theme',
    language: 'Language',
    switchTheme: 'Change theme',
    switchLanguage: 'Change language',
    settingsSoon: 'The settings view will be added in the next pass.',
    approvalApproved: 'Change approved. The agent can continue.',
    approvalRejected: 'Change rejected. The session is paused.',
    jobCancelled: 'Job safely cancelled.',
    jobRetried: 'Job restarted from the last stable phase.',
    messageSent: 'Simulated response added to the thread.',
    fileCount: '1,248 files',
    sourceCount: '2 local sources',
    previewMode: 'Preview mode',
    simulatedData: 'Simulated data · No backend connection',
    backToWorkspace: 'Back to workspace',
    viewDetails: 'View details',
    settingsTitle: 'System settings',
    settingsSub: 'Configure the local experience, models, and TrinaxAI trust boundaries.',
    settingsGeneral: 'General',
    settingsModels: 'Models',
    settingsKnowledge: 'Knowledge',
    settingsNetwork: 'Network & pairing',
    settingsPrivacy: 'Privacy',
    settingsAppearance: 'Appearance & experience',
    settingsAppearanceSub: 'Customize how your local workspace feels.',
    settingsTheme: 'Interface theme',
    settingsLanguage: 'Interface language',
    settingsSound: 'Activity sounds',
    settingsSoundSub: 'Play a signal while TrinaxAI is working.',
    settingsRuntime: 'Local runtime',
    settingsRuntimeSub: 'This prototype represents a local host managed by you.',
    settingsActiveModel: 'Active chat model',
    settingsModelSub: 'Reused when the model is already loaded in Ollama.',
    settingsHardware: 'Hardware profile',
    settingsHardwareValue: '16 GB · Local GPU detected',
    settingsKnowledgeTitle: 'Sources & retrieval',
    settingsKnowledgeSub: 'Choose which knowledge supports automatic answers.',
    settingsDefaultCollection: 'Default collection',
    settingsCollectionSub: 'Used when Knowledge mode does not specify another collection.',
    settingsAutoIndex: 'Automatic indexing',
    settingsAutoIndexSub: 'Detect new documents in watched folders.',
    settingsNetworkTitle: 'Gateway & devices',
    settingsNetworkSub: 'Control how other devices reach this local host.',
    settingsGateway: 'PWA gateway',
    settingsGatewaySub: 'Only the gateway is exposed to the local network.',
    settingsPairing: 'Device pairing',
    settingsPairingSub: 'Remote devices receive explicit, revocable scopes.',
    settingsPrivacyTitle: 'Privacy & trust',
    settingsPrivacySub: 'TrinaxAI keeps data and inference close to your machine.',
    settingsInference: 'Local inference',
    settingsInferenceSub: 'Responses are processed through Ollama on this host.',
    settingsTelemetry: 'Product telemetry',
    settingsTelemetrySub: 'Usage events are not sent in this configuration.',
    settingsSaved: 'Settings saved in this preview.',
    saveChanges: 'Save changes',
    settingsLocal: 'Local',
    settingsProtected: 'Protected',
    settingsSelect: 'Select',
    settingsEnabled: 'Enabled',
    settingsDisabled: 'Disabled',
    status: 'Status',
  },
};

const sessions = [
  { id: 'architecture', title: 'Decisiones de arquitectura', titleEn: 'Architecture decisions', preview: 'Gateway, loopback y límites de confianza', previewEn: 'Gateway, loopback and trust boundaries', day: 'today' },
  { id: 'release', title: 'Preparación de release', titleEn: 'Release readiness', preview: 'Paridad del instalador y puertas de validación', previewEn: 'Installer parity and validation gates', day: 'today' },
  { id: 'research', title: 'Notas de investigación local', titleEn: 'Local research notes', preview: 'Evidencia de la colección de producto', previewEn: 'Evidence from the product collection', day: 'yesterday' },
];

const collections = [
  { id: 'product', name: 'Product docs', documents: 184, chunks: 1248, tone: 'blue' },
  { id: 'security', name: 'Security & trust', documents: 62, chunks: 421, tone: 'teal' },
  { id: 'release', name: 'Release notes', documents: 28, chunks: 173, tone: 'amber' },
];

const documents = [
  { id: 'architecture', name: 'ARCHITECTURE.md', collection: 'product', type: 'Markdown', chunks: 42, updated: 'Today · 09:42' },
  { id: 'security', name: 'SECURITY.md', collection: 'security', type: 'Markdown', chunks: 31, updated: 'Yesterday · 18:20' },
  { id: 'api', name: 'API_REFERENCE.md', collection: 'product', type: 'Markdown', chunks: 86, updated: 'Yesterday · 14:08' },
];

const sources = [
  { id: 'source-1', name: 'ARCHITECTURE.md', path: 'docs / ARCHITECTURE.md', page: '§ 3. Runtime', score: '0.94', excerpt: 'The PWA gateway is the only LAN-exposed boundary. FastAPI and Ollama remain on loopback by default.' },
  { id: 'source-2', name: 'SECURITY.md', path: 'docs / SECURITY.md', page: '§ 4. Device scopes', score: '0.88', excerpt: 'Remote devices receive explicit scopes. System administration and agent execution remain host-only by default.' },
];

const activityItems = [
  { time: '09:42', label: 'Embedding batch 04 completed', tone: 'success' },
  { time: '09:41', label: 'Indexed docs / ARCHITECTURE.md', tone: 'blue' },
  { time: '09:39', label: '42 chunks persisted', tone: 'muted' },
];

function getInitialLocale(): Locale {
  if (typeof navigator !== 'undefined' && navigator.languages.some((language) => language.toLowerCase().startsWith('en'))) return 'en';
  return 'es';
}

function getInitialTheme(): Theme {
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: light)').matches) return 'light';
  return 'dark';
}

function IconButton({ label, children, onClick, active = false, className = '' }: { label: string; children: ReactNode; onClick?: () => void; active?: boolean; className?: string }) {
  return (
    <button aria-label={label} className={`icon-button ${active ? 'is-active' : ''} ${className}`} onClick={onClick} type="button">
      {children}
    </button>
  );
}

function StatusDot({ tone = 'blue' }: { tone?: 'blue' | 'green' | 'amber' | 'red' }) {
  return <span aria-hidden="true" className={`status-dot status-dot-${tone}`} />;
}

function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'blue' | 'teal' | 'amber' | 'red' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function App() {
  const [locale, setLocale] = useState<Locale>(getInitialLocale);
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [activeView, setActiveView] = useState<View>('chat');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(() => typeof window === 'undefined' || !window.matchMedia('(max-width: 900px)').matches);
  const [chatMode, setChatMode] = useState<'knowledge' | 'chat'>('knowledge');
  const [chatInput, setChatInput] = useState('');
  const [sentPrompts, setSentPrompts] = useState<string[]>([]);
  const [toast, setToast] = useState('');
  const [selectedCollection, setSelectedCollection] = useState('product');
  const [knowledgeQuery, setKnowledgeQuery] = useState('');
  const [agentDecision, setAgentDecision] = useState<AgentDecision>('pending');
  const [yoloEnabled, setYoloEnabled] = useState(false);
  const [yoloConfirmOpen, setYoloConfirmOpen] = useState(false);
  const [indexingState, setIndexingState] = useState<IndexingState>('running');
  const [settingsSection, setSettingsSection] = useState<SettingsSection>('general');
  const [activeModel, setActiveModel] = useState('qwen3:14b');
  const [defaultCollection, setDefaultCollection] = useState('product');
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [autoIndexEnabled, setAutoIndexEnabled] = useState(true);
  const [gatewayEnabled, setGatewayEnabled] = useState(true);
  const [telemetryEnabled, setTelemetryEnabled] = useState(false);

  const ui = translations[locale];
  const selectedCollectionData = collections.find((collection) => collection.id === selectedCollection) ?? collections[0];

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  const visibleDocuments = documents.filter((document) => {
    const matchesCollection = document.collection === selectedCollection;
    const normalizedQuery = knowledgeQuery.trim().toLowerCase();
    return matchesCollection && (!normalizedQuery || document.name.toLowerCase().includes(normalizedQuery));
  });

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast((current) => current === message ? '' : current), 3200);
  };

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
  };

  const toggleLocale = () => setLocale((current) => current === 'es' ? 'en' : 'es');

  const navigate = (view: View) => {
    setActiveView(view);
    setMobileNavOpen(false);
  };

  const submitChat = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = chatInput.trim();
    if (!value) return;
    setSentPrompts((current) => [...current, value]);
    setChatInput('');
    showToast(ui.messageSent);
  };

  const seedMessages = useMemo(() => locale === 'es'
    ? [
      { role: 'user' as const, content: '¿Cómo protege TrinaxAI el acceso desde la red local?', time: '09:38' },
      { role: 'assistant' as const, content: `${ui.responseIntro}\n\n${ui.responseBody}`, time: '09:39' },
    ]
    : [
      { role: 'user' as const, content: 'How does TrinaxAI protect access from the local network?', time: '09:38' },
      { role: 'assistant' as const, content: `${ui.responseIntro}\n\n${ui.responseBody}`, time: '09:39' },
    ], [locale, ui.responseBody, ui.responseIntro]);

  const messageList = [
    ...seedMessages,
    ...sentPrompts.flatMap((prompt, index) => [
      { role: 'user' as const, content: prompt, time: `09:${40 + index}` },
      { role: 'assistant' as const, content: locale === 'es' ? 'La respuesta simulada está lista para revisar en el siguiente pase de diseño.' : 'The simulated answer is ready to review in the next design pass.', time: `09:${41 + index}` },
    ]),
  ];

  const showContextRail = contextOpen && activeView !== 'settings';

  return (
    <div className="preview-app">
      <a className="skip-link" href="#main-content">{locale === 'es' ? 'Saltar al contenido' : 'Skip to content'}</a>
      <div aria-hidden="true" className="ambient-canvas">
        <span className="wave wave-one" />
        <span className="wave wave-two" />
        <span className="wave wave-three" />
      </div>

      <header className="topbar">
        <div className="topbar-start">
          <IconButton className="mobile-only" label={locale === 'es' ? 'Abrir navegación' : 'Open navigation'} onClick={() => setMobileNavOpen(true)}>
            <IconMenu />
          </IconButton>
          <button className="brand-lockup" onClick={() => navigate('chat')} type="button">
            <img alt="TrinaxAI" height="34" src="/logo-for-ai-transparent.webp" width="34" />
            <span>
              <strong translate="no">TrinaxAI</strong>
              <small>{ui.brandSubtitle}</small>
            </span>
          </button>
        </div>
        <div className="topbar-end">
          <span className="preview-chip"><span className="preview-chip-pulse" />{ui.previewMode}</span>
          <span className="local-chip"><IconLock size={13} />{ui.localPrivate}</span>
          <IconButton label={ui.switchTheme} onClick={toggleTheme}>{theme === 'dark' ? <IconSun /> : <IconMoon />}</IconButton>
          <button aria-label={ui.switchLanguage} className="locale-button" onClick={toggleLocale} type="button">{locale.toUpperCase()}</button>
        </div>
      </header>

      <div className={`workspace-grid ${showContextRail ? '' : 'context-collapsed'} ${activeView === 'settings' ? 'settings-active' : ''}`}>
        {mobileNavOpen && <button aria-label={locale === 'es' ? 'Cerrar navegación' : 'Close navigation'} className="mobile-scrim" onClick={() => setMobileNavOpen(false)} type="button" />}
        <Sidebar activeView={activeView} locale={locale} navigate={navigate} onClose={() => setMobileNavOpen(false)} open={mobileNavOpen} showToast={showToast} ui={ui} />

        <main className="main-column" id="main-content" tabIndex={-1}>
          <div className="mobile-context-bar">
            <span><StatusDot tone="green" /> {ui.online}</span>
            <button onClick={() => setContextOpen((current) => !current)} type="button"><IconPanel size={15} />{contextOpen ? ui.hideContext : ui.showContext}</button>
          </div>
          {activeView === 'chat' && <ChatView chatInput={chatInput} chatMode={chatMode} locale={locale} messageList={messageList} onChatModeChange={() => setChatMode((current) => current === 'knowledge' ? 'chat' : 'knowledge')} onInputChange={setChatInput} onSubmit={submitChat} onToggleContext={() => setContextOpen((current) => !current)} ui={ui} />}
          {activeView === 'knowledge' && <KnowledgeView knowledgeQuery={knowledgeQuery} locale={locale} onCollectionChange={setSelectedCollection} onQueryChange={setKnowledgeQuery} selectedCollection={selectedCollection} selectedCollectionData={selectedCollectionData} ui={ui} visibleDocuments={visibleDocuments} />}
          {activeView === 'agent' && <AgentView agentDecision={agentDecision} locale={locale} onDecision={(decision) => { setAgentDecision(decision); showToast(decision === 'approved' ? ui.approvalApproved : ui.approvalRejected); }} onYoloCancel={() => setYoloConfirmOpen(false)} onYoloConfirm={() => { setYoloEnabled(true); setYoloConfirmOpen(false); showToast(ui.yoloTitle); }} onYoloRequest={() => setYoloConfirmOpen(true)} onYoloReset={() => setYoloEnabled(false)} ui={ui} yoloConfirmOpen={yoloConfirmOpen} yoloEnabled={yoloEnabled} />}
          {activeView === 'indexing' && <IndexingView indexingState={indexingState} onCancel={() => { setIndexingState('failed'); showToast(ui.jobCancelled); }} onRetry={() => { setIndexingState('running'); showToast(ui.jobRetried); }} ui={ui} />}
          {activeView === 'settings' && <SettingsView activeModel={activeModel} autoIndexEnabled={autoIndexEnabled} defaultCollection={defaultCollection} gatewayEnabled={gatewayEnabled} locale={locale} onAutoIndexChange={setAutoIndexEnabled} onCollectionChange={setDefaultCollection} onGatewayChange={setGatewayEnabled} onModelChange={setActiveModel} onSectionChange={setSettingsSection} onSoundChange={setSoundEnabled} onTelemetryChange={setTelemetryEnabled} onThemeChange={setTheme} section={settingsSection} soundEnabled={soundEnabled} telemetryEnabled={telemetryEnabled} theme={theme} ui={ui} onSave={() => showToast(ui.settingsSaved)} />}
        </main>

        <ContextRail contextOpen={contextOpen} locale={locale} onClose={() => setContextOpen(false)} ui={ui} />
      </div>

      <div aria-atomic="true" aria-live="polite" className={`toast-region ${toast ? 'is-visible' : ''}`} role="status">{toast}</div>
      <footer className="preview-footer"><span>{ui.simulatedData}</span><span>v0.1 · TrinaxCode</span></footer>
    </div>
  );
}

function Sidebar({ activeView, locale, navigate, onClose, open, showToast, ui }: { activeView: View; locale: Locale; navigate: (view: View) => void; onClose: () => void; open: boolean; showToast: (message: string) => void; ui: Record<TranslationKey, string> }) {
  const navItems: { view: View; label: string; icon: ReactNode }[] = [
    { view: 'chat', label: ui.navWorkspace, icon: <IconMessage /> },
    { view: 'knowledge', label: ui.navKnowledge, icon: <IconBook /> },
    { view: 'agent', label: ui.navAgent, icon: <IconBot /> },
    { view: 'indexing', label: ui.navIndexing, icon: <IconDatabase /> },
  ];

  return (
    <aside aria-label={locale === 'es' ? 'Navegación principal' : 'Main navigation'} className={`sidebar ${open ? 'is-open' : ''}`}>
      <div className="sidebar-head">
        <span className="sidebar-section-label">{ui.workspace}</span>
        <IconButton className="mobile-only" label={locale === 'es' ? 'Cerrar navegación' : 'Close navigation'} onClick={onClose}><IconX /></IconButton>
      </div>
      <nav className="primary-nav">
        {navItems.map((item) => (
          <button aria-current={activeView === item.view ? 'page' : undefined} className={`nav-item ${activeView === item.view ? 'is-active' : ''}`} key={item.view} onClick={() => navigate(item.view)} type="button">
            <span className="nav-item-icon">{item.icon}</span>
            <span>{item.label}</span>
            {item.view === 'chat' && <span className="nav-item-count">3</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar-divider" />
      <div className="sidebar-section-head"><span>{ui.recent}</span><IconButton label={ui.newChat} onClick={() => { navigate('chat'); showToast(ui.newChat); }}><IconPlus size={16} /></IconButton></div>
      <div className="session-search"><IconSearch size={15} /><input aria-label={ui.searchChats} autoComplete="off" name="chat-search" placeholder={ui.searchChats} type="search" /><kbd><IconCommand size={11} />K</kbd></div>
      <div className="session-list">
        <span className="session-day">{ui.today}</span>
        {sessions.filter((session) => session.day === 'today').map((session, index) => <SessionItem key={session.id} active={index === 0} locale={locale} session={session} />)}
        <span className="session-day session-day-spaced">{ui.yesterday}</span>
        {sessions.filter((session) => session.day === 'yesterday').map((session) => <SessionItem key={session.id} active={false} locale={locale} session={session} />)}
      </div>
      <div className="sidebar-bottom">
        <button aria-current={activeView === 'settings' ? 'page' : undefined} className={`sidebar-settings ${activeView === 'settings' ? 'is-active' : ''}`} onClick={() => navigate('settings')} type="button"><IconSettings size={17} /><span>{ui.navSettings}</span><IconChevronRight className="sidebar-settings-arrow" size={15} /></button>
        <div className="device-mini-card"><span className="device-avatar"><IconShield size={15} /></span><span><strong>{ui.hostLocal}</strong><small>{ui.localPrivate}</small></span><StatusDot tone="green" /></div>
      </div>
    </aside>
  );
}

function SessionItem({ active, locale, session }: { active: boolean; locale: Locale; session: typeof sessions[number] }) {
  return (
    <button aria-current={active ? 'page' : undefined} className={`session-item ${active ? 'is-active' : ''}`} type="button">
      <span className="session-icon"><IconMessage size={15} /></span>
      <span className="session-copy"><strong>{locale === 'en' ? session.titleEn : session.title}</strong><small>{locale === 'en' ? session.previewEn : session.preview}</small></span>
      {active && <span className="session-active-dot" />}
    </button>
  );
}

function ChatView({ chatInput, chatMode, locale, messageList, onChatModeChange, onInputChange, onSubmit, onToggleContext, ui }: { chatInput: string; chatMode: 'knowledge' | 'chat'; locale: Locale; messageList: { role: 'user' | 'assistant'; content: string; time: string }[]; onChatModeChange: () => void; onInputChange: (value: string) => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void; onToggleContext: () => void; ui: Record<TranslationKey, string> }) {
  return (
    <div className="view-shell chat-view">
      <div className="view-toolbar">
        <div className="view-title-block"><span className="eyebrow"><span className="eyebrow-line" />{ui.workspace}</span><h1>{ui.workspaceHeadline}</h1><p>{ui.workspaceSub}</p></div>
        <div className="view-toolbar-actions"><button className="context-toggle" onClick={onToggleContext} type="button"><IconPanel size={15} />{ui.context}<span className="context-toggle-dot" /></button><button className="mode-select" onClick={onChatModeChange} type="button"><IconSpark size={15} />{chatMode === 'knowledge' ? ui.knowledgeMode : ui.chatMode}<IconChevronDown size={14} /></button><Badge tone="blue"><StatusDot tone="green" />{ui.localReady}</Badge></div>
      </div>

      <section aria-label={locale === 'es' ? 'Conversación actual' : 'Current conversation'} className="chat-surface">
        <div className="chat-surface-head"><div><span className="surface-kicker">{ui.assistantLabel}</span><span className="surface-meta">q4 · {ui.model} <strong translate="no">qwen3:14b</strong></span></div><IconButton label={locale === 'es' ? 'Más opciones' : 'More options'}><IconMore /></IconButton></div>
        <div className="message-stream">
          {messageList.map((message, index) => message.role === 'user'
            ? <div className="message-row message-row-user" key={`${index}-${message.role}`}><div className="message-time">{message.time}</div><div className="user-bubble">{message.content}</div></div>
            : <div className="message-row message-row-assistant" key={`${index}-${message.role}`}><div className="assistant-avatar"><img alt="" height="25" src="/logo-for-ai-transparent.webp" width="25" /></div><div className="assistant-message"><div className="assistant-message-head"><strong>{ui.assistantLabel}</strong><span>{message.time}</span></div><div className="assistant-copy">{message.content.split('\n\n').map((paragraph) => <p key={paragraph}>{paragraph}</p>)}</div>{index === 1 && <SourcePreview ui={ui} />}</div></div>)}
        </div>
        <form className="composer" onSubmit={onSubmit}>
          <div className="composer-tools"><IconButton label={ui.attach}><IconPaperclip /></IconButton><span className="composer-mode"><span className="composer-mode-dot" />{chatMode === 'knowledge' ? ui.knowledgeMode : ui.chatMode}<IconChevronDown size={13} /></span></div>
          <label className="sr-only" htmlFor="preview-prompt">{ui.composerPlaceholder}</label><input autoComplete="off" id="preview-prompt" name="prompt" onChange={(event) => onInputChange(event.target.value)} placeholder={ui.composerPlaceholder} spellCheck="true" type="text" value={chatInput} />
          <div className="composer-end"><IconButton label={ui.voice}><IconMic /></IconButton><button aria-label={ui.send} className="send-button" disabled={!chatInput.trim()} type="submit"><IconArrowUp size={18} /></button></div>
          <span className="composer-hint">{ui.composerHint}</span>
        </form>
      </section>
    </div>
  );
}

function SettingsView({ activeModel, autoIndexEnabled, defaultCollection, gatewayEnabled, locale, onAutoIndexChange, onCollectionChange, onGatewayChange, onModelChange, onSectionChange, onSave, onSoundChange, onTelemetryChange, onThemeChange, section, soundEnabled, telemetryEnabled, theme, ui }: { activeModel: string; autoIndexEnabled: boolean; defaultCollection: string; gatewayEnabled: boolean; locale: Locale; onAutoIndexChange: (value: boolean) => void; onCollectionChange: (value: string) => void; onGatewayChange: (value: boolean) => void; onModelChange: (value: string) => void; onSectionChange: (value: SettingsSection) => void; onSave: () => void; onSoundChange: (value: boolean) => void; onTelemetryChange: (value: boolean) => void; onThemeChange: (value: Theme) => void; section: SettingsSection; soundEnabled: boolean; telemetryEnabled: boolean; theme: Theme; ui: Record<TranslationKey, string> }) {
  const sections: { id: SettingsSection; label: string; icon: ReactNode }[] = [
    { id: 'general', label: ui.settingsGeneral, icon: <IconSliders size={16} /> },
    { id: 'models', label: ui.settingsModels, icon: <IconSpark size={16} /> },
    { id: 'knowledge', label: ui.settingsKnowledge, icon: <IconBook size={16} /> },
    { id: 'network', label: ui.settingsNetwork, icon: <IconGlobe size={16} /> },
    { id: 'privacy', label: ui.settingsPrivacy, icon: <IconShield size={16} /> },
  ];

  const sectionMeta: Record<SettingsSection, { title: string; sub: string; eyebrow: string; tone: string }> = {
    general: { title: ui.settingsAppearance, sub: ui.settingsAppearanceSub, eyebrow: ui.settingsGeneral, tone: 'blue' },
    models: { title: ui.settingsRuntime, sub: ui.settingsRuntimeSub, eyebrow: ui.settingsModels, tone: 'teal' },
    knowledge: { title: ui.settingsKnowledgeTitle, sub: ui.settingsKnowledgeSub, eyebrow: ui.settingsKnowledge, tone: 'teal' },
    network: { title: ui.settingsNetworkTitle, sub: ui.settingsNetworkSub, eyebrow: ui.settingsNetwork, tone: 'amber' },
    privacy: { title: ui.settingsPrivacyTitle, sub: ui.settingsPrivacySub, eyebrow: ui.settingsPrivacy, tone: 'purple' },
  };
  const meta = sectionMeta[section];

  return (
    <div className="view-shell settings-view">
      <div className="settings-heading">
        <div className="view-title-block"><span className={`eyebrow eyebrow-${meta.tone}`}><span className="eyebrow-line" />{meta.eyebrow}</span><h1>{ui.settingsTitle}</h1><p>{ui.settingsSub}</p></div>
        <div className="settings-heading-status"><Badge tone="teal"><StatusDot tone="green" />{ui.settingsLocal}</Badge><span>{ui.settingsProtected}</span></div>
      </div>
      <div className="settings-layout">
        <nav aria-label={locale === 'es' ? 'Secciones de ajustes' : 'Settings sections'} className="settings-nav">
          <span className="surface-kicker">{locale === 'es' ? 'Configurar' : 'Configure'}</span>
          <div className="settings-nav-list">{sections.map((item) => <button aria-current={section === item.id ? 'page' : undefined} className={`settings-nav-item ${section === item.id ? 'is-active' : ''}`} key={item.id} onClick={() => onSectionChange(item.id)} type="button"><span>{item.icon}</span>{item.label}<IconChevronRight className="settings-nav-arrow" size={14} /></button>)}</div>
          <div className="settings-nav-note"><IconLock size={15} /><span><strong>{ui.settingsProtected}</strong><small>{locale === 'es' ? 'Solo el host local administra estos controles.' : 'Only the local host manages these controls.'}</small></span></div>
        </nav>
        <section aria-labelledby="settings-section-title" className="settings-panel">
          <div className="settings-panel-heading"><div><span className={`settings-section-mark mark-${meta.tone}`} /><span className="surface-kicker">{meta.eyebrow}</span><h2 id="settings-section-title">{meta.title}</h2><p>{meta.sub}</p></div><IconButton label={ui.viewDetails}><IconMore /></IconButton></div>
          {section === 'general' && <><SettingGroup title={ui.settingsAppearance} sub={ui.settingsAppearanceSub}><SettingRow icon={<IconSun size={17} />} label={ui.settingsTheme} description={theme === 'dark' ? 'Midnight operations' : 'Clear daylight'}><SegmentedControl ariaLabel={ui.settingsTheme} options={[{ label: 'Dark', value: 'dark' }, { label: 'Light', value: 'light' }]} value={theme} onChange={(value) => onThemeChange(value as Theme)} /></SettingRow><SettingRow icon={<IconGlobe size={17} />} label={ui.settingsLanguage} description={locale === 'es' ? 'Español' : 'English'}><span className="settings-value-pill">{locale.toUpperCase()}</span></SettingRow><SettingRow icon={<IconActivity size={17} />} label={ui.settingsSound} description={ui.settingsSoundSub}><SettingSwitch checked={soundEnabled} label={soundEnabled ? ui.settingsEnabled : ui.settingsDisabled} onChange={onSoundChange} /></SettingRow></SettingGroup><SettingGroup title={ui.settingsRuntime} sub={ui.settingsRuntimeSub}><StatusSettingRow icon={<IconServer size={17} />} label={ui.fastapi} value={ui.connected} tone="green" /><StatusSettingRow icon={<IconSpark size={17} />} label={ui.ollama} value={ui.connected} tone="green" /><StatusSettingRow icon={<IconDatabase size={17} />} label={ui.indexStatus} value={ui.synced} tone="blue" /></SettingGroup></>}
          {section === 'models' && <><SettingGroup title={ui.settingsRuntime} sub={ui.settingsRuntimeSub}><SettingRow icon={<IconSpark size={17} />} label={ui.settingsActiveModel} description={ui.settingsModelSub}><select aria-label={ui.settingsActiveModel} className="settings-select" name="active-model" onChange={(event) => onModelChange(event.target.value)} value={activeModel}><option value="qwen3:14b">qwen3:14b · General</option><option value="llama3.2:8b">llama3.2:8b · Fast</option><option value="qwen2.5-coder:14b">qwen2.5-coder:14b · Agent</option></select></SettingRow><SettingRow icon={<IconActivity size={17} />} label={ui.settingsHardware} description={ui.settingsHardwareValue}><Badge tone="teal"><StatusDot tone="green" />{ui.ready}</Badge></SettingRow></SettingGroup><div className="settings-callout callout-teal"><IconShield size={18} /><div><strong>{ui.settingsLocal}</strong><p>{locale === 'es' ? 'Los modelos se ejecutan en Ollama. No hay proveedor cloud configurado en esta preview.' : 'Models run through Ollama. No cloud provider is configured in this preview.'}</p></div></div></>}
          {section === 'knowledge' && <><SettingGroup title={ui.settingsKnowledgeTitle} sub={ui.settingsKnowledgeSub}><SettingRow icon={<IconBook size={17} />} label={ui.settingsDefaultCollection} description={ui.settingsCollectionSub}><select aria-label={ui.settingsDefaultCollection} className="settings-select" name="default-collection" onChange={(event) => onCollectionChange(event.target.value)} value={defaultCollection}>{collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}</select></SettingRow><SettingRow icon={<IconDatabase size={17} />} label={ui.settingsAutoIndex} description={ui.settingsAutoIndexSub}><SettingSwitch checked={autoIndexEnabled} label={autoIndexEnabled ? ui.settingsEnabled : ui.settingsDisabled} onChange={onAutoIndexChange} /></SettingRow><StatusSettingRow icon={<IconCheck size={17} />} label={ui.localKnowledge} value={ui.synced} tone="green" /></SettingGroup></>}
          {section === 'network' && <><SettingGroup title={ui.settingsNetworkTitle} sub={ui.settingsNetworkSub}><SettingRow icon={<IconPanel size={17} />} label={ui.settingsGateway} description={ui.settingsGatewaySub}><SettingSwitch checked={gatewayEnabled} label={gatewayEnabled ? ui.settingsEnabled : ui.settingsDisabled} onChange={onGatewayChange} /></SettingRow><SettingRow icon={<IconShield size={17} />} label={ui.settingsPairing} description={ui.settingsPairingSub}><Badge tone="teal"><StatusDot tone="green" />{ui.ready}</Badge></SettingRow></SettingGroup><div className="paired-device-list"><div className="paired-device-head"><span className="surface-kicker">{ui.pairedDevice}</span><Badge tone="blue">1</Badge></div><div className="paired-device"><span className="permission-avatar"><IconLock size={15} /></span><span><strong>{ui.hostLocal}</strong><small>{ui.deviceScope}</small></span><StatusDot tone="green" /></div></div></>}
          {section === 'privacy' && <><SettingGroup title={ui.settingsPrivacyTitle} sub={ui.settingsPrivacySub}><SettingRow icon={<IconLock size={17} />} label={ui.settingsInference} description={ui.settingsInferenceSub}><Badge tone="teal"><IconCheck size={13} />{ui.settingsLocal}</Badge></SettingRow><SettingRow icon={<IconGlobe size={17} />} label={ui.settingsTelemetry} description={ui.settingsTelemetrySub}><SettingSwitch checked={telemetryEnabled} label={telemetryEnabled ? ui.settingsEnabled : ui.settingsDisabled} onChange={onTelemetryChange} /></SettingRow></SettingGroup><div className="settings-callout callout-blue"><IconShield size={18} /><div><strong>{ui.settingsProtected}</strong><p>{locale === 'es' ? 'Los secretos, tokens y credenciales no viven en esta UI de prueba.' : 'Secrets, tokens, and credentials do not live in this preview UI.'}</p></div></div></>}
          <div className="settings-footer"><span>{ui.simulatedData}</span><button className="button button-primary" onClick={onSave} type="button"><IconCheck size={15} />{ui.saveChanges}</button></div>
        </section>
      </div>
    </div>
  );
}

function SettingGroup({ children, sub, title }: { children: ReactNode; sub: string; title: string }) {
  return <section className="setting-group"><div className="setting-group-head"><h3>{title}</h3><p>{sub}</p></div><div className="setting-group-body">{children}</div></section>;
}

function SettingRow({ children, description, icon, label }: { children: ReactNode; description: string; icon: ReactNode; label: string }) {
  return <div className="setting-row"><span className="setting-row-icon">{icon}</span><span className="setting-row-copy"><strong>{label}</strong><small>{description}</small></span><span className="setting-row-control">{children}</span></div>;
}

function StatusSettingRow({ icon, label, tone, value }: { icon: ReactNode; label: string; tone: 'green' | 'blue'; value: string }) {
  return <div className="setting-row"><span className="setting-row-icon">{icon}</span><span className="setting-row-copy"><strong>{label}</strong><small>Local service</small></span><span className={`settings-status settings-status-${tone}`}><StatusDot tone={tone === 'green' ? 'green' : 'blue'} />{value}</span></div>;
}

function SettingSwitch({ checked, label, onChange }: { checked: boolean; label: string; onChange: (value: boolean) => void }) {
  return <button aria-checked={checked} className={`settings-switch ${checked ? 'is-on' : ''}`} onClick={() => onChange(!checked)} role="switch" type="button"><span /> <small>{label}</small></button>;
}

function SegmentedControl({ ariaLabel, onChange, options, value }: { ariaLabel: string; onChange: (value: string) => void; options: { label: string; value: string }[]; value: string }) {
  return <div aria-label={ariaLabel} className="segmented-control" role="group">{options.map((option) => <button aria-pressed={value === option.value} className={value === option.value ? 'is-selected' : ''} key={option.value} onClick={() => onChange(option.value)} type="button">{option.label}</button>)}</div>;
}

function SourcePreview({ ui }: { ui: Record<TranslationKey, string> }) {
  return (
    <div className="source-preview"><div className="source-preview-head"><span><IconBook size={14} />{ui.sources}</span><Badge tone="teal">{ui.sourceCount}</Badge></div><div className="source-list">{sources.map((source) => <div className="source-row" key={source.id}><span className="source-file-icon"><IconFile size={15} /></span><span className="source-row-copy"><strong>{source.name}</strong><small>{source.path} · {source.page}</small></span><span className="source-score">{source.score}</span></div>)}</div><button className="text-link" type="button">{ui.openKnowledge}<IconExternal size={13} /></button></div>
  );
}

function KnowledgeView({ knowledgeQuery, locale, onCollectionChange, onQueryChange, selectedCollection, selectedCollectionData, ui, visibleDocuments }: { knowledgeQuery: string; locale: Locale; onCollectionChange: (id: string) => void; onQueryChange: (value: string) => void; selectedCollection: string; selectedCollectionData: typeof collections[number]; ui: Record<TranslationKey, string>; visibleDocuments: typeof documents }) {
  return (
    <div className="view-shell">
      <div className="view-toolbar"><div className="view-title-block"><span className="eyebrow"><span className="eyebrow-line eyebrow-line-teal" />{ui.navKnowledge}</span><h1>{ui.knowledgeTitle}</h1><p>{ui.knowledgeSub}</p></div><Badge tone="teal"><IconDatabase size={14} />{ui.localKnowledge}</Badge></div>
      <div className="knowledge-layout"><section className="collection-panel"><div className="panel-title-row"><div><span className="surface-kicker">{ui.collections}</span><strong>3</strong></div><IconButton label={ui.newChat}><IconPlus size={16} /></IconButton></div><div className="collection-list">{collections.map((collection) => <button className={`collection-item ${selectedCollection === collection.id ? 'is-active' : ''}`} key={collection.id} onClick={() => onCollectionChange(collection.id)} type="button"><span className={`collection-glyph collection-glyph-${collection.tone}`}><IconFolder size={16} /></span><span><strong>{collection.name}</strong><small>{collection.documents} {ui.documents.toLowerCase()}</small></span><IconChevronRight className="collection-chevron" size={15} /></button>)}</div><div className="collection-summary"><span className="summary-orbit"><IconActivity size={16} /></span><span><strong>{ui.synced}</strong><small>1.842 {ui.chunks.toLowerCase()}</small></span></div></section><section className="document-panel"><div className="document-panel-head"><div><span className="surface-kicker">{ui.documents}</span><h2>{selectedCollectionData.name}</h2></div><div className="document-tools"><label className="knowledge-search"><IconSearch size={15} /><span className="sr-only">{ui.searchKnowledge}</span><input aria-label={ui.searchKnowledge} autoComplete="off" name="knowledge-search" onChange={(event) => onQueryChange(event.target.value)} placeholder={ui.searchKnowledge} type="search" value={knowledgeQuery} /></label><IconButton label={ui.viewDetails}><IconSliders size={16} /></IconButton></div></div><div className="document-table-head"><span>{ui.allSources}</span><span>{ui.chunks}</span><span>{ui.status}</span></div><div className="document-list">{visibleDocuments.length > 0 ? visibleDocuments.map((document) => <button className="document-row" key={document.id} type="button"><span className="document-name"><span className="document-icon"><IconFile size={16} /></span><span><strong>{document.name}</strong><small>{document.type} · {document.updated}</small></span></span><span className="document-count">{document.chunks}</span><span className="document-status"><StatusDot tone="green" />{ui.ready}<IconChevronRight size={14} /></span></button>) : <div className="empty-state"><IconSearch size={21} /><strong>{locale === 'es' ? 'No hay evidencia coincidente' : 'No matching evidence'}</strong><span>{locale === 'es' ? 'Prueba otra búsqueda o selecciona otra colección.' : 'Try another search or select another collection.'}</span></div>}</div></section></div>
    </div>
  );
}

function AgentView({ agentDecision, locale, onDecision, onYoloCancel, onYoloConfirm, onYoloRequest, onYoloReset, ui, yoloConfirmOpen, yoloEnabled }: { agentDecision: AgentDecision; locale: Locale; onDecision: (decision: AgentDecision) => void; onYoloCancel: () => void; onYoloConfirm: () => void; onYoloRequest: () => void; onYoloReset: () => void; ui: Record<TranslationKey, string>; yoloConfirmOpen: boolean; yoloEnabled: boolean }) {
  return (
    <div className="view-shell">
      <div className="view-toolbar"><div className="view-title-block"><span className="eyebrow"><span className="eyebrow-line eyebrow-line-amber" />{ui.navAgent}</span><h1>{ui.agentTitle}</h1><p>{ui.agentSub}</p></div><Badge tone={yoloEnabled ? 'red' : 'neutral'}><IconShield size={14} />{yoloEnabled ? ui.yolo : ui.normal}</Badge></div>
      <div className="agent-layout"><section className="agent-main-panel"><div className="agent-toolbar"><div className="agent-context"><span className="agent-context-icon"><IconFolder size={16} /></span><span><small>{ui.workspacePath}</small><strong translate="no">~/Projects/trinaxai</strong></span></div><div className="agent-context"><span className="agent-model-icon"><IconSpark size={16} /></span><span><small>{ui.modelLabel}</small><strong translate="no">qwen2.5-coder:14b</strong></span></div></div><div className="activity-heading"><span className="surface-kicker">{ui.activity}</span><Badge tone="amber"><span className="activity-pulse" />{agentDecision === 'pending' ? ui.approvalPending : agentDecision === 'approved' ? ui.approvalApproved : ui.approvalRejected}</Badge></div><div className="agent-timeline"><TimelineItem active icon={<IconSpark size={15} />} label={ui.planning} detail={locale === 'es' ? 'Separando cambios de interfaz y estado.' : 'Separating interface and state changes.'} /><TimelineItem active icon={<IconFile size={15} />} label={ui.reading} detail={locale === 'es' ? 'Revisando 4 archivos relevantes.' : 'Reviewing 4 relevant files.'} /><TimelineItem active={agentDecision === 'pending'} icon={<IconShield size={15} />} label={ui.approvalPending} detail={locale === 'es' ? 'Una acción peligrosa necesita tu decisión.' : 'A dangerous action needs your decision.'} />{agentDecision !== 'pending' && <TimelineItem active icon={agentDecision === 'approved' ? <IconCheck size={15} /> : <IconX size={15} />} label={agentDecision === 'approved' ? ui.approvalApproved : ui.approvalRejected} detail={locale === 'es' ? 'Estado simulado para revisar el flujo.' : 'Simulated state for reviewing the flow.'} last />}</div>{agentDecision === 'pending' ? <ApprovalCard locale={locale} onApprove={() => onDecision('approved')} onReject={() => onDecision('rejected')} ui={ui} /> : <div className={`decision-banner ${agentDecision}`}><span className="decision-icon">{agentDecision === 'approved' ? <IconCheck size={18} /> : <IconX size={18} />}</span><span><strong>{agentDecision === 'approved' ? ui.approvalApproved : ui.approvalRejected}</strong><small>{ui.safeWorkspace}</small></span><button className="text-link" onClick={() => onDecision('pending')} type="button">{locale === 'es' ? 'Restablecer' : 'Reset'}</button></div>}</section><aside className="agent-side-panel"><div className="side-panel-title"><span className="surface-kicker">{ui.status}</span><IconMore size={17} /></div><div className="agent-status-card"><div className="status-card-icon"><IconLock size={18} /></div><strong>{ui.safeWorkspace}</strong><p>{locale === 'es' ? 'Las acciones de escritura se muestran antes de ejecutarse.' : 'Write actions are shown before execution.'}</p></div><div className="yolo-control"><div className="yolo-control-head"><span><strong>{ui.yolo}</strong><small>{locale === 'es' ? 'Modo sin confirmación' : 'No-confirmation mode'}</small></span><button aria-checked={yoloEnabled} className={`switch ${yoloEnabled ? 'is-on' : ''}`} onClick={yoloEnabled ? onYoloReset : onYoloRequest} role="switch" type="button"><span /></button></div>{yoloConfirmOpen && <div className="yolo-warning"><IconAlert size={16} /><p><strong>{ui.yoloTitle}</strong>{ui.yoloBody}</p><div><button className="button button-danger" onClick={onYoloConfirm} type="button">{ui.enableYolo}</button><button className="button button-quiet" onClick={onYoloCancel} type="button">{ui.cancel}</button></div></div>}</div></aside></div>
    </div>
  );
}

function TimelineItem({ active, detail, icon, label, last = false }: { active: boolean; detail: string; icon: ReactNode; label: string; last?: boolean }) {
  return <div className={`timeline-item ${active ? 'is-active' : ''} ${last ? 'is-last' : ''}`}><span className="timeline-marker">{icon}</span><span className="timeline-line" /><div><strong>{label}</strong><small>{detail}</small></div></div>;
}

function ApprovalCard({ locale, onApprove, onReject, ui }: { locale: Locale; onApprove: () => void; onReject: () => void; ui: Record<TranslationKey, string> }) {
  return <div className="approval-card"><div className="approval-card-head"><div><Badge tone="amber"><IconCode size={13} />write_file</Badge><span>{ui.approvalTitle}</span></div><span className="approval-id">approval_08</span></div><div className="approval-file"><IconFile size={16} /><code translate="no">app/routes/agent.py</code><span>+18 −4</span></div><div className="diff-preview"><span className="diff-line diff-remove">− &nbsp;return await run_agent(request)</span><span className="diff-line diff-add">+ &nbsp;return await run_agent(request, sandbox=True)</span><span className="diff-line diff-add">+ &nbsp;assert workspace.isolated</span></div><div className="approval-impact"><span><IconAlert size={15} />{ui.impact}</span><strong>{locale === 'es' ? 'Modifica código del workspace' : 'Modifies workspace code'}</strong></div><div className="approval-actions"><button className="button button-primary" onClick={onApprove} type="button"><IconCheck size={16} />{ui.approve}</button><button className="button button-quiet" onClick={onReject} type="button">{ui.reject}</button></div></div>;
}

function IndexingView({ indexingState, onCancel, onRetry, ui }: { indexingState: IndexingState; onCancel: () => void; onRetry: () => void; ui: Record<TranslationKey, string> }) {
  const progress = indexingState === 'completed' ? 100 : indexingState === 'failed' ? 68 : 68;
  return <div className="view-shell"><div className="view-toolbar"><div className="view-title-block"><span className="eyebrow"><span className="eyebrow-line eyebrow-line-purple" />{ui.navIndexing}</span><h1>{ui.indexTitle}</h1><p>{ui.indexSub}</p></div><Badge tone={indexingState === 'failed' ? 'red' : indexingState === 'completed' ? 'teal' : 'blue'}><StatusDot tone={indexingState === 'failed' ? 'red' : indexingState === 'completed' ? 'green' : 'blue'} />{indexingState === 'running' ? ui.embedding : indexingState === 'completed' ? ui.indexingDone : ui.approvalRejected}</Badge></div><div className="indexing-layout"><section className="index-job-card"><div className="index-job-head"><div><span className="surface-kicker">{ui.activeJob}</span><h2 translate="no">product-docs · 8d3c</h2></div><IconButton label={ui.viewDetails}><IconMore /></IconButton></div><div className="index-progress-copy"><span>{ui.embedding}</span><strong>{progress}%</strong></div><div aria-label={`${progress}%`} aria-valuemax={100} aria-valuemin={0} aria-valuenow={progress} className="progress-track" role="progressbar"><span style={{ width: `${progress}%` }} /></div><div className="index-metrics"><Metric icon={<IconFile size={16} />} label={ui.files} value="184 / 272" /><Metric icon={<IconDatabase size={16} />} label={ui.chunksGenerated} value="1,248" /><Metric icon={<IconClock size={16} />} label={ui.elapsed} value="04:38" /></div><div className="index-job-actions">{indexingState === 'running' ? <button className="button button-quiet" onClick={onCancel} type="button">{ui.cancelJob}</button> : <button className="button button-primary" onClick={onRetry} type="button"><IconRotate size={15} />{ui.retryJob}</button>}<button className="button button-quiet" type="button">{ui.viewDetails}<IconChevronRight size={15} /></button></div></section><section className="activity-panel"><div className="panel-title-row"><span className="surface-kicker">{ui.recentActivity}</span><Badge tone="neutral">{ui.fileCount}</Badge></div><div className="activity-list">{activityItems.map((item) => <div className="activity-row" key={item.time}><span className={`activity-icon activity-icon-${item.tone}`}><IconCheck size={14} /></span><span><strong>{item.label}</strong><small>{item.time}</small></span></div>)}</div><div className="index-tip"><IconSpark size={16} /><span>{ui.safeWorkspace}</span></div></section></div></div>;
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="metric"><span className="metric-icon">{icon}</span><span><small>{label}</small><strong>{value}</strong></span></div>;
}

function ContextRail({ contextOpen, locale, onClose, ui }: { contextOpen: boolean; locale: Locale; onClose: () => void; ui: Record<TranslationKey, string> }) {
  return <aside aria-label={ui.contextTitle} className={`context-rail ${contextOpen ? 'is-open' : ''}`}><div className="context-head"><div><span className="eyebrow"><span className="eyebrow-line" />{ui.context}</span><h2>{ui.contextTitle}</h2></div><IconButton className="context-close" label={ui.hideContext} onClick={onClose}><IconX size={17} /></IconButton></div><section className="rail-section"><div className="rail-section-head"><span>{ui.online}</span><span className="rail-live"><StatusDot tone="green" />{ui.ready}</span></div><div className="health-list"><HealthRow icon={<IconServer size={15} />} label={ui.fastapi} value={ui.connected} tone="green" /><HealthRow icon={<IconSpark size={15} />} label={ui.ollama} value={ui.connected} tone="green" /><HealthRow icon={<IconDatabase size={15} />} label={ui.indexStatus} value={ui.synced} tone="blue" /><HealthRow icon={<IconGlobe size={15} />} label={ui.webSearch} value={ui.available} tone="amber" /><HealthRow icon={<IconMic size={15} />} label={ui.voiceStatus} value={ui.disabled} tone="muted" /></div></section><section className="rail-section"><div className="rail-section-head"><span>{ui.activeContext}</span><button className="rail-link" type="button">{ui.viewDetails}</button></div><div className="active-context-card"><div className="active-context-icon"><IconBook size={17} /></div><div><strong>{ui.localKnowledge}</strong><span>Product docs</span></div><Badge tone="teal">RAG</Badge><div className="context-tags"><span>architecture</span><span>security</span><span>api</span></div></div></section><section className="rail-section"><div className="rail-section-head"><span>{ui.memory}</span><IconMore size={16} /></div><div className="memory-card"><span className="memory-type">preference</span><p>{locale === 'es' ? 'Mantener una UI bilingüe y local-first.' : 'Keep the UI bilingual and local-first.'}</p><small>inferred · 0.92</small></div></section><section className="rail-section rail-permission"><div className="rail-section-head"><span>{ui.permissions}</span><IconShield size={15} /></div><div className="permission-card"><div className="permission-avatar"><IconLock size={15} /></div><div><strong>{ui.pairedDevice}</strong><span>{ui.deviceScope}</span></div><StatusDot tone="green" /></div></section></aside>;
}

function HealthRow({ icon, label, tone, value }: { icon: ReactNode; label: string; tone: 'green' | 'blue' | 'amber' | 'muted'; value: string }) {
  return <div className="health-row"><span className="health-icon">{icon}</span><span>{label}</span><span className={`health-value health-value-${tone}`}><StatusDot tone={tone === 'muted' ? 'amber' : tone === 'blue' ? 'blue' : tone} />{value}</span></div>;
}

export default App;
