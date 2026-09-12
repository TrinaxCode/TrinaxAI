import { useEffect, useRef, useState } from 'react';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { APP_CONFIG } from '../lib/config';
import BackButton from './BackButton';
import ChatMarkdown from './chat/ChatMarkdown';
import './chat/chat.css';

type Section =
  | 'intro'
  | 'about'
  | 'install'
  | 'config'
  | 'models'
  | 'indexing'
  | 'agent'
  | 'research'
  | 'files'
  | 'security'
  | 'api'
  | 'pwa'
  | 'troubleshoot'
  | 'contributing'
  | 'community';

interface DocLink {
  file: string;
  labelEs: string;
  labelEn: string;
}

interface DocSection {
  id: Section;
  labelEs: string;
  labelEn: string;
  summaryEs: string;
  summaryEn: string;
  links: DocLink[];
}

const sections: DocSection[] = [
  {
    id: 'intro', labelEs: 'Introducción', labelEn: 'Introduction',
    summaryEs: 'Qué es TrinaxAI, qué permanece local y cuándo usa Internet.',
    summaryEn: 'What TrinaxAI is, what stays local, and when it uses the Internet.',
    links: [{ file: 'README.md', labelEs: 'Resumen del proyecto', labelEn: 'Project overview' }],
  },
  {
    id: 'about', labelEs: 'Acerca de', labelEn: 'About',
    summaryEs: 'Historia, principios y contexto del proyecto.',
    summaryEn: 'Project history, principles, and context.',
    links: [{ file: 'README.md', labelEs: 'Visión y principios', labelEn: 'Vision and principles' }],
  },
  {
    id: 'install', labelEs: 'Instalación', labelEn: 'Installation',
    summaryEs: 'Instala con un comando desde la URL y consulta la guía de tu sistema.',
    summaryEn: 'Install with one URL command and follow the guide for your system.',
    links: [
      { file: 'INSTALL_LINUX.md', labelEs: 'Linux', labelEn: 'Linux' },
      { file: 'INSTALL_MACOS.md', labelEs: 'macOS', labelEn: 'macOS' },
      { file: 'INSTALL_WINDOWS.md', labelEs: 'Windows', labelEn: 'Windows' },
    ],
  },
  {
    id: 'config', labelEs: 'Configuración', labelEn: 'Configuration',
    summaryEs: 'Variables de entorno, perfiles, límites y recuperación.',
    summaryEn: 'Environment variables, profiles, limits, and recovery.',
    links: [
      { file: 'CONFIGURATION.md', labelEs: 'Referencia de configuración', labelEn: 'Configuration reference' },
      { file: 'ENVIRONMENT_VARIABLES.md', labelEs: 'Variables de entorno', labelEn: 'Environment variables' },
    ],
  },
  {
    id: 'models', labelEs: 'Modelos', labelEn: 'Models',
    summaryEs: 'Perfiles de hardware, modelos locales y mediciones.',
    summaryEn: 'Hardware profiles, local models, and measurements.',
    links: [{ file: 'MODEL_BENCHMARK.md', labelEs: 'Benchmark y límites', labelEn: 'Benchmark and limits' }],
  },
  {
    id: 'indexing', labelEs: 'Indexación', labelEn: 'Indexing',
    summaryEs: 'Fuentes locales, colecciones, fragmentos y almacenamiento vectorial SQLite.',
    summaryEn: 'Local sources, collections, chunks, and SQLite vector storage.',
    links: [
      { file: 'ARCHITECTURE.md', labelEs: 'Flujo y almacenamiento', labelEn: 'Flow and storage' },
      { file: 'CONFIGURATION.md', labelEs: 'Opciones de RAG', labelEn: 'RAG options' },
    ],
  },
  {
    id: 'agent', labelEs: 'Agente', labelEn: 'Agent',
    summaryEs: 'El agente se activa de forma explícita y opera dentro de workspaces autorizados.',
    summaryEn: 'The agent is enabled explicitly and operates inside authorized workspaces.',
    links: [
      { file: 'CLI_REFERENCE.md', labelEs: 'Referencia de CLI', labelEn: 'CLI reference' },
      { file: 'SECURITY.md', labelEs: 'Sandbox y permisos', labelEn: 'Sandbox and permissions' },
    ],
  },
  {
    id: 'research', labelEs: 'Internet e investigación', labelEn: 'Internet & Research',
    summaryEs: 'Búsqueda web opcional, proveedores y lectura segura de páginas.',
    summaryEn: 'Optional web search, providers, and safe page reading.',
    links: [
      { file: 'API_REFERENCE.md', labelEs: 'API de búsqueda', labelEn: 'Search API' },
      { file: 'CONFIGURATION.md', labelEs: 'Configuración web', labelEn: 'Web configuration' },
    ],
  },
  {
    id: 'files', labelEs: 'Archivos', labelEn: 'Files',
    summaryEs: 'Adjuntos, colecciones, memoria y datos privados del host.',
    summaryEn: 'Attachments, collections, memory, and private host data.',
    links: [{ file: 'ARCHITECTURE.md', labelEs: 'Datos y almacenamiento', labelEn: 'Data and storage' }],
  },
  {
    id: 'security', labelEs: 'Seguridad', labelEn: 'Security',
    summaryEs: 'Pairing, scopes, gateway, sandboxing y límites de confianza.',
    summaryEn: 'Pairing, scopes, gateway, sandboxing, and trust boundaries.',
    links: [
      { file: 'SECURITY.md', labelEs: 'Política de seguridad', labelEn: 'Security policy' },
      { file: 'NETWORK_PAIRING.md', labelEs: 'Pairing y HTTPS', labelEn: 'Pairing and HTTPS' },
    ],
  },
  {
    id: 'api', labelEs: 'Referencia de API', labelEn: 'API Reference',
    summaryEs: 'Endpoints, autenticación, SSE y contratos HTTP.',
    summaryEn: 'Endpoints, authentication, SSE, and HTTP contracts.',
    links: [{ file: 'API_REFERENCE.md', labelEs: 'Referencia HTTP', labelEn: 'HTTP reference' }],
  },
  {
    id: 'pwa', labelEs: 'Guía de PWA', labelEn: 'PWA Guide',
    summaryEs: 'Uso desde escritorio, móvil, HTTPS local y sincronización.',
    summaryEn: 'Desktop and mobile use, local HTTPS, and synchronization.',
    links: [{ file: 'chat-pwa/README.md', labelEs: 'Documentación de la PWA', labelEn: 'PWA documentation' }],
  },
  {
    id: 'troubleshoot', labelEs: 'Solución de problemas', labelEn: 'Troubleshooting',
    summaryEs: 'Diagnóstico y recuperación segura de instalaciones y servicios.',
    summaryEn: 'Diagnostics and safe recovery for installations and services.',
    links: [{ file: 'TROUBLESHOOTING.md', labelEs: 'Guía de recuperación', labelEn: 'Recovery guide' }],
  },
  {
    id: 'contributing', labelEs: 'Contribuir', labelEn: 'Contributing',
    summaryEs: 'Convenciones, pruebas y flujo de contribución.',
    summaryEn: 'Conventions, tests, and the contribution workflow.',
    links: [
      { file: 'CONTRIBUTING.md', labelEs: 'Guía de contribución', labelEn: 'Contribution guide' },
      { file: 'DEVELOPER_GUIDE.md', labelEs: 'Guía de desarrollo', labelEn: 'Developer guide' },
    ],
  },
  {
    id: 'community', labelEs: 'Proyecto y comunidad', labelEn: 'Project & Community',
    summaryEs: 'Soporte, cambios, licencia, marca y verificación de releases.',
    summaryEn: 'Support, changes, licensing, branding, and release verification.',
    links: [
      { file: 'SUPPORT.md', labelEs: 'Soporte', labelEn: 'Support' },
      { file: 'CHANGELOG.md', labelEs: 'Registro de cambios', labelEn: 'Changelog' },
      { file: 'TESTING.md', labelEs: 'Guía de pruebas', labelEn: 'Testing guide' },
      { file: 'RELEASE_SIGNING.md', labelEs: 'Firma de releases', labelEn: 'Release signing' },
      { file: 'CODE_OF_CONDUCT.md', labelEs: 'Código de conducta', labelEn: 'Code of conduct' },
      { file: 'TRADEMARK.md', labelEs: 'Marca', labelEn: 'Trademark' },
    ],
  },
];

const rootDocFiles = new Set(['README.md', 'TESTING.md']);

function localizedFile(file: string, isEs: boolean): string {
  return isEs ? file.replace(/\.md$/, '.es.md') : file;
}

function docAssetUrl(file: string, isEs: boolean): string {
  const localized = localizedFile(file, isEs);
  const assetPath = rootDocFiles.has(file) || file.startsWith('chat-pwa/') || file.startsWith('docs/')
    ? localized
    : `docs/${localized}`;
  return `/docs-content/${assetPath}`;
}

function documentBody(markdown: string | undefined): string {
  return (markdown || '')
    .replace(/^\s*<h1[\s\S]*?<\/h1>\s*/i, '')
    .replace(/^\s*(?:<p[\s\S]*?<\/p>\s*){1,3}/i, '')
    .trim();
}

function repositoryPath(file: string): string {
  return rootDocFiles.has(file) || file.startsWith('chat-pwa/') || file.startsWith('docs/') ? file : `docs/${file}`;
}

function resolveDocumentLink(file: string, href: string | undefined): string | undefined {
  if (!href || href.startsWith('#') || href.startsWith('/') || /^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(href)) {
    return href;
  }

  try {
    const target = new URL(href, `https://docs.invalid/${repositoryPath(file)}`);
    const path = target.pathname.replace(/^\/+/, '');
    return `${APP_CONFIG.repoUrl}/blob/main/${path}${target.search}${target.hash}`;
  } catch {
    return href;
  }
}

const docUrl = (file: string) => {
  return `${APP_CONFIG.repoUrl}/blob/main/${repositoryPath(file)}`;
};

export default function Docs({ onBack }: { onBack: () => void }) {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const [active, setActive] = useState<Section>('intro');
  const [documents, setDocuments] = useState<Record<string, string>>({});
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const contentRef = useRef<HTMLElement>(null);
  const selected = sections.find((section) => section.id === active) ?? sections[0];
  const isEs = lang === 'es';
  const textMain = isDark ? 'text-white' : 'text-gray-900';
  const textSub = isDark ? 'text-white/65' : 'text-gray-600';
  const textMuted = isDark ? 'text-white/45' : 'text-gray-500';
  const card = isDark ? 'border-white/[0.08] bg-white/[0.02]' : 'border-gray-200 bg-white';
  const activeLink = isDark ? 'bg-[#006bbd]/15 text-[#006bbd]' : 'bg-[#006bbd]/10 text-[#006bbd]';
  const inactiveLink = isDark ? 'text-white/50 hover:bg-white/[0.04] hover:text-white/80' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800';

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, left: 0 });
  }, [active, isEs]);

  useEffect(() => {
    let cancelled = false;
    setDocuments({});
    setDocumentsLoading(true);

    Promise.all(selected.links.map(async (link) => {
      try {
        const response = await fetch(docAssetUrl(link.file, isEs));
        if (!response.ok) return null;
        return [link.file, await response.text()] as const;
      } catch {
        return null;
      }
    })).then((entries) => {
      if (!cancelled) setDocuments(Object.fromEntries(entries.filter((entry): entry is readonly [string, string] => entry !== null)));
    }).finally(() => {
      if (!cancelled) setDocumentsLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [active, isEs]);

  return (
    <div className="docs-page flex h-full min-w-0 max-w-full flex-col overflow-hidden bg-transparent">
      <div className="page-header flex shrink-0 items-center gap-3 px-4 pb-3 pt-[env(safe-area-inset-top,0px)]">
        <BackButton onClick={onBack} label={t('docsBack')} isDark={isDark} className="-ml-2" />
        <span className={`text-sm font-medium ${isDark ? 'text-white/80' : 'text-gray-800'}`}>{t('docsTitle')}</span>
        <img src="/logo-for-ai-transparent.webp" alt="TrinaxAI" translate="no" className="ml-auto h-14 w-14 rounded-full object-contain" width={56} height={56} draggable={false} />
      </div>

      <div className="flex min-h-0 min-w-0 max-w-full flex-1">
        <aside className="hidden w-44 shrink-0 overflow-y-auto px-2 py-4 md:block lg:w-52 lg:px-3">
          <nav aria-label={isEs ? 'Secciones de documentación' : 'Documentation sections'} className="space-y-0.5">
            {sections.map((section) => (
              <button
                key={section.id}
                type="button"
                onClick={() => setActive(section.id)}
                aria-current={active === section.id ? 'page' : undefined}
                className={`w-full rounded-lg px-3 py-2 text-left text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${active === section.id ? activeLink : inactiveLink}`}
              >
                {isEs ? section.labelEs : section.labelEn}
              </button>
            ))}
          </nav>
        </aside>

        <main
          ref={contentRef}
          id="docs-content"
          tabIndex={-1}
          aria-label={isEs ? 'Contenido de documentación' : 'Documentation content'}
          className="docs-content min-w-0 max-w-full flex-1 overflow-y-auto overflow-x-hidden px-3 py-5 [overflow-wrap:anywhere] sm:px-4 sm:py-6 md:max-w-3xl"
        >
          <a href="#docs-content" className="sr-only focus:not-sr-only focus:absolute focus:z-10 focus:rounded-lg focus:bg-[#006bbd] focus:px-3 focus:py-2 focus:text-sm focus:text-white">
            {isEs ? 'Saltar al contenido' : 'Skip to content'}
          </a>
          <div className="mb-5 md:hidden">
            <label htmlFor="docs-section" className={`sr-only ${textMuted}`}>{isEs ? 'Seleccionar sección' : 'Select section'}</label>
            <select
              id="docs-section"
              value={active}
              onChange={(event) => setActive(event.target.value as Section)}
              className={`w-full appearance-none rounded-xl border px-3 py-2.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${card} ${textMain}`}
            >
              {sections.map((section) => <option key={section.id} value={section.id}>{isEs ? section.labelEs : section.labelEn}</option>)}
            </select>
          </div>

          <section className={`rounded-2xl border p-5 sm:p-6 ${card}`} aria-labelledby="docs-section-title">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#006bbd]">{isEs ? 'Guía integrada' : 'Integrated guide'}</p>
            <h1 id="docs-section-title" className={`mt-2 text-2xl font-bold ${textMain}`}>{isEs ? selected.labelEs : selected.labelEn}</h1>
            <p className={`mt-3 text-sm leading-relaxed ${textSub}`}>{isEs ? selected.summaryEs : selected.summaryEn}</p>
            <div className="mt-6 space-y-6">
              {selected.links.map((link) => (
                <article key={link.file} className={`rounded-xl border p-4 sm:p-5 ${card}`}>
                  <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-current/10 pb-3">
                    <h2 className={`text-base font-semibold ${textMain}`}>{isEs ? link.labelEs : link.labelEn}</h2>
                    <a
                      href={docUrl(link.file)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-medium text-[#006bbd] underline decoration-1 underline-offset-2 hover:text-[#4aa7ed]"
                    >
                      {isEs ? 'Abrir referencia' : 'Open reference'} ↗
                    </a>
                  </div>
                  {documents[link.file] !== undefined ? (
                    <ChatMarkdown
                      text={documentBody(documents[link.file])}
                      isDark={isDark}
                      resolveLink={(href) => resolveDocumentLink(link.file, href)}
                    />
                  ) : documentsLoading ? (
                    <p role="status" aria-live="polite" className={`text-sm ${textSub}`}>{isEs ? 'Cargando documentación…' : 'Loading documentation…'}</p>
                  ) : (
                    <p role="status" aria-live="polite" className={`text-sm ${textSub}`}>
                      {isEs ? 'Esta referencia no está disponible en este build.' : 'This reference is not available in this build.'}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </section>

          <p className={`mt-5 text-center text-xs leading-relaxed ${textMuted}`}>
            {isEs
              ? 'La guía se incluye en la PWA para consultarla sin salir de la aplicación; cada enlace abre la referencia canónica del repositorio.'
              : 'The guide is bundled into the PWA for in-app reading; each link opens the canonical repository reference.'}
          </p>
        </main>
      </div>
    </div>
  );
}
