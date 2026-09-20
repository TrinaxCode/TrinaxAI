import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react';
import { MdChevronRight, MdExpandMore, MdOpenInNew } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { APP_CONFIG } from '../lib/config';
import { formatAppRoute, type DocsSection } from '../lib/appRoute';
import BackButton from './BackButton';
import ChatMarkdown from './chat/ChatMarkdown';
import './chat/chat.css';

interface DocLink {
  file: string;
  labelEs: string;
  labelEn: string;
}

interface DocSection {
  id: DocsSection;
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
    summaryEs: 'Instala con npm y consulta la guía de tu sistema.',
    summaryEn: 'Install with npm and follow the guide for your system.',
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

function pick(item: { labelEs: string; labelEn: string }, isEs: boolean): string {
  return isEs ? item.labelEs : item.labelEn;
}

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

function ArticleSkeleton({ isDark }: { isDark: boolean }) {
  const bar = isDark ? 'bg-white/[0.07]' : 'bg-gray-200';
  const widths = ['w-11/12', 'w-full', 'w-10/12', 'w-9/12', 'w-full', 'w-6/12'];
  return (
    <div className="docs-skeleton space-y-3" aria-hidden="true">
      {widths.map((width, index) => (
        <div key={`${width}-${index}`} className={`docs-skeleton-bar h-3.5 rounded-full ${bar} ${width}`} />
      ))}
    </div>
  );
}

interface Props {
  onBack: () => void;
  initialSection?: DocsSection;
  onSectionChange?: (section: DocsSection) => void;
}

export default function Docs({ onBack, initialSection = 'intro', onSectionChange }: Props) {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const [active, setActive] = useState<DocsSection>(initialSection);
  const [documents, setDocuments] = useState<Record<string, string>>({});
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const contentRef = useRef<HTMLElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const focusContentRef = useRef(false);
  const isEs = lang === 'es';
  const activeIndex = sections.findIndex((section) => section.id === active);
  const selected = sections[activeIndex] ?? sections[0];
  const previous = activeIndex > 0 ? sections[activeIndex - 1] : undefined;
  const next = activeIndex >= 0 && activeIndex < sections.length - 1 ? sections[activeIndex + 1] : undefined;
  const referenceCount = selected.links.length;
  const textMain = isDark ? 'text-white' : 'text-gray-900';
  const textSub = isDark ? 'text-white/65' : 'text-gray-600';
  const textMuted = isDark ? 'text-white/55' : 'text-gray-500';
  const card = isDark ? 'border-white/[0.08] bg-white/[0.02]' : 'border-gray-200 bg-white';
  const brandText = isDark ? 'text-[#4aa7ed]' : 'text-[#006bbd]';
  const activeLink = isDark ? 'bg-[#4aa7ed]/15 text-[#4aa7ed]' : 'bg-[#006bbd]/10 text-[#006bbd]';
  const inactiveLink = isDark ? 'text-white/60 hover:bg-white/[0.05] hover:text-white/90' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900';
  const navCardHover = isDark ? 'hover:border-white/20' : 'hover:border-gray-300';

  useEffect(() => {
    setActive(initialSection);
  }, [initialSection]);

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, left: 0 });
    if (!focusContentRef.current) return;
    focusContentRef.current = false;
    titleRef.current?.focus({ preventScroll: true });
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

  const selectSection = useCallback((section: DocsSection) => {
    focusContentRef.current = true;
    setActive(section);
    onSectionChange?.(section);
  }, [onSectionChange]);

  const handleSectionLink = (event: MouseEvent<HTMLAnchorElement>, section: DocsSection) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    selectSection(section);
  };

  return (
    <div className="docs-page flex h-full min-w-0 max-w-full flex-col overflow-hidden bg-transparent">
      <div className="page-header shrink-0 px-4 pb-3 pt-[env(safe-area-inset-top,0px)]">
        <div className="flex items-center gap-3">
          <BackButton onClick={onBack} label={t('docsBack')} isDark={isDark} className="-ml-2" />
          <span className={`text-sm font-medium ${isDark ? 'text-white/80' : 'text-gray-800'}`}>{t('docsTitle')}</span>
          <img src="/logo-for-ai-transparent.webp" alt="TrinaxAI" translate="no" className="ml-auto h-10 w-10 shrink-0 rounded-full object-contain" width={40} height={40} draggable={false} />
        </div>

        <div className="relative mt-2 md:hidden">
          <label htmlFor="docs-section" className="sr-only">{isEs ? 'Seleccionar sección' : 'Select section'}</label>
          <select
            id="docs-section"
            value={active}
            onChange={(event) => selectSection(event.target.value as DocsSection)}
            className={`min-h-11 w-full appearance-none rounded-xl border px-3 pr-10 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${card} ${textMain}`}
          >
            {sections.map((section) => <option key={section.id} value={section.id}>{pick(section, isEs)}</option>)}
          </select>
          <MdExpandMore size={18} aria-hidden="true" className={`pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 ${textSub}`} />
        </div>
      </div>

      <div className="flex min-h-0 min-w-0 max-w-full flex-1">
        <aside className="hidden w-56 shrink-0 overflow-y-auto overscroll-contain px-2 py-4 md:block lg:w-64 lg:px-3">
          <p className={`px-3 pb-2 text-[0.68rem] font-semibold uppercase tracking-[0.18em] ${textMuted}`}>
            {isEs ? 'Índice' : 'Contents'}
          </p>
          <nav aria-label={isEs ? 'Secciones de documentación' : 'Documentation sections'}>
            <ul className="space-y-0.5">
              {sections.map((section, index) => {
                const isActive = section.id === active;
                return (
                  <li key={section.id}>
                    <a
                      href={formatAppRoute({ page: 'docs', docsSection: section.id })}
                      onClick={(event) => handleSectionLink(event, section.id)}
                      aria-current={isActive ? 'page' : undefined}
                      className={`group flex min-h-11 items-center gap-2.5 rounded-xl py-2 pl-3 pr-2 text-[0.8rem] font-medium leading-snug transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isActive ? activeLink : inactiveLink}`}
                    >
                      <span aria-hidden="true" className={`w-5 shrink-0 text-[0.68rem] tabular-nums ${isActive ? brandText : textMuted}`}>
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <span className="min-w-0 flex-1">{pick(section, isEs)}</span>
                      <MdChevronRight size={14} aria-hidden="true" className={`shrink-0 transition-opacity ${isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-50'}`} />
                    </a>
                  </li>
                );
              })}
            </ul>
          </nav>
        </aside>

        <main
          ref={contentRef}
          id="docs-content"
          tabIndex={-1}
          aria-label={isEs ? 'Contenido de documentación' : 'Documentation content'}
          className="docs-content min-w-0 max-w-full flex-1 overflow-y-auto overflow-x-hidden overscroll-contain px-3 py-5 [overflow-wrap:anywhere] sm:px-4 sm:py-6 md:max-w-3xl"
        >
          <div key={`${active}:${lang}`} className="docs-section">
            <div className="flex flex-wrap items-center gap-2">
              <p className={`text-[0.68rem] font-semibold uppercase tracking-[0.18em] ${brandText}`}>
                {isEs ? 'Guía integrada' : 'Integrated guide'}
              </p>
              <span className={`h-1 w-1 rounded-full ${isDark ? 'bg-white/20' : 'bg-gray-300'}`} aria-hidden="true" />
              <span className={`text-[0.68rem] font-medium ${textMuted}`}>
                {referenceCount === 1
                  ? (isEs ? '1 referencia' : '1 reference')
                  : (isEs ? `${referenceCount} referencias` : `${referenceCount} references`)}
              </span>
            </div>

            <h1
              id="docs-section-title"
              ref={titleRef}
              tabIndex={-1}
              className={`mt-2 rounded-lg text-2xl font-semibold tracking-tight text-balance outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed]/60 ${textMain}`}
            >
              {pick(selected, isEs)}
            </h1>
            <p className={`mt-3 max-w-prose text-sm leading-relaxed text-pretty ${textSub}`}>
              {isEs ? selected.summaryEs : selected.summaryEn}
            </p>

            <div className="mt-7 space-y-8">
              {selected.links.map((link) => (
                <article key={link.file} className="docs-article">
                  <div className={`mb-4 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b pb-3 ${isDark ? 'border-white/[0.07]' : 'border-gray-200'}`}>
                    <h2 className={`text-base font-semibold tracking-tight ${textMain}`}>{pick(link, isEs)}</h2>
                    <a
                      href={docUrl(link.file)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${brandText} ${isDark ? 'hover:bg-white/[0.06]' : 'hover:bg-[#006bbd]/10'}`}
                    >
                      {isEs ? 'Abrir en GitHub' : 'Open on GitHub'}
                      <MdOpenInNew size={13} aria-hidden="true" />
                    </a>
                  </div>
                  {documents[link.file] !== undefined ? (
                    <ChatMarkdown
                      text={documentBody(documents[link.file])}
                      isDark={isDark}
                      resolveLink={(href) => resolveDocumentLink(link.file, href)}
                    />
                  ) : documentsLoading ? (
                    <div role="status" aria-live="polite">
                      <span className="sr-only">{isEs ? 'Cargando documentación…' : 'Loading documentation…'}</span>
                      <ArticleSkeleton isDark={isDark} />
                    </div>
                  ) : (
                    <div role="status" className={`rounded-xl border border-dashed px-4 py-3 text-sm ${card} ${textSub}`}>
                      <p>{isEs ? 'Esta referencia no está incluida en este build de la PWA.' : 'This reference is not bundled in this build of the PWA.'}</p>
                      <a
                        href={docUrl(link.file)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`mt-1.5 inline-flex items-center gap-1 font-medium underline decoration-1 underline-offset-2 ${brandText}`}
                      >
                        {isEs ? 'Leerla en GitHub' : 'Read it on GitHub'}
                        <MdOpenInNew size={13} aria-hidden="true" />
                      </a>
                    </div>
                  )}
                </article>
              ))}
            </div>

            <nav aria-label={isEs ? 'Navegación entre secciones' : 'Section navigation'} className="mt-10 grid gap-3 sm:grid-cols-2">
              {previous ? (
                <a
                  href={formatAppRoute({ page: 'docs', docsSection: previous.id })}
                  onClick={(event) => handleSectionLink(event, previous.id)}
                  aria-label={`${isEs ? 'Anterior' : 'Previous'}: ${pick(previous, isEs)}`}
                  className={`flex min-h-11 flex-col justify-center rounded-2xl border px-4 py-3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${card} ${navCardHover}`}
                >
                  <span className={`text-[0.68rem] font-semibold uppercase tracking-[0.16em] ${textMuted}`}>{isEs ? 'Anterior' : 'Previous'}</span>
                  <span className={`mt-1 text-sm font-semibold ${textMain}`}>{pick(previous, isEs)}</span>
                </a>
              ) : (
                <span aria-hidden="true" className="hidden sm:block" />
              )}
              {next ? (
                <a
                  href={formatAppRoute({ page: 'docs', docsSection: next.id })}
                  onClick={(event) => handleSectionLink(event, next.id)}
                  aria-label={`${isEs ? 'Siguiente' : 'Next'}: ${pick(next, isEs)}`}
                  className={`flex min-h-11 flex-col justify-center rounded-2xl border px-4 py-3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] sm:items-end sm:text-right ${card} ${navCardHover}`}
                >
                  <span className={`text-[0.68rem] font-semibold uppercase tracking-[0.16em] ${textMuted}`}>{isEs ? 'Siguiente' : 'Next'}</span>
                  <span className={`mt-1 text-sm font-semibold ${textMain}`}>{pick(next, isEs)}</span>
                </a>
              ) : null}
            </nav>

            <p className={`mt-6 text-center text-xs leading-relaxed ${textMuted}`}>
              {isEs
                ? 'La guía se incluye en la PWA para consultarla sin salir de la aplicación; cada enlace abre la referencia canónica del repositorio.'
                : 'The guide is bundled into the PWA for in-app reading; each link opens the canonical repository reference.'}
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
