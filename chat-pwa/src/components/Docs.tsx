import { useState } from 'react';
import { motion } from 'framer-motion';
import { MdArrowBack } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';

interface Props { onBack: () => void; }

type Section = 'intro' | 'about' | 'install' | 'config' | 'models' | 'indexing' | 'agent' | 'research' | 'files' | 'security' | 'api' | 'pwa' | 'troubleshoot' | 'contributing';

interface DocSection {
  id: Section;
  labelEs: string;
  labelEn: string;
  icon: string;
}

const sections: DocSection[] = [
  { id: 'intro', labelEs: 'Introduccion', labelEn: 'Introduction', icon: '' },
  { id: 'about', labelEs: 'Acerca de', labelEn: 'About', icon: '' },
  { id: 'install', labelEs: 'Instalacion', labelEn: 'Installation', icon: '' },
  { id: 'config', labelEs: 'Configuracion', labelEn: 'Configuration', icon: '' },
  { id: 'models', labelEs: 'Modelos', labelEn: 'Models', icon: '' },
  { id: 'indexing', labelEs: 'Indexacion', labelEn: 'Indexing', icon: '' },
  { id: 'agent', labelEs: 'Agente', labelEn: 'Agent', icon: '' },
  { id: 'research', labelEs: 'Internet e investigacion', labelEn: 'Internet & research', icon: '' },
  { id: 'files', labelEs: 'Archivos', labelEn: 'Files', icon: '' },
  { id: 'security', labelEs: 'Seguridad', labelEn: 'Security', icon: '' },
  { id: 'api', labelEs: 'Referencia de API', labelEn: 'API Reference', icon: '' },
  { id: 'pwa', labelEs: 'Guía de PWA', labelEn: 'PWA Guide', icon: '' },
  { id: 'troubleshoot', labelEs: 'Solucion de problemas', labelEn: 'Troubleshooting', icon: '' },
  { id: 'contributing', labelEs: 'Contribuir', labelEn: 'Contributing', icon: '' },
];

export default function Docs({ onBack }: Props) {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const [active, setActive] = useState<Section>('intro');

  const textMain = isDark ? 'text-white' : 'text-gray-900';
  const textSub = isDark ? 'text-white/60' : 'text-gray-600';
  const textMuted = isDark ? 'text-white/40' : 'text-gray-400';
  const sidebarBg = isDark ? 'bg-white/[0.02] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const activeLink = isDark ? 'bg-[#006bbd]/15 text-[#006bbd]' : 'bg-[#006bbd]/10 text-[#006bbd]';
  const inactiveLink = isDark ? 'text-white/50 hover:text-white/80 hover:bg-white/[0.04]' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100';
  const codeBg = isDark ? 'bg-black/40 border-white/[0.08] max-w-full' : 'bg-gray-100 border-gray-200 max-w-full';
  const sectionBg = isDark ? 'bg-white/[0.02] border-white/[0.06] min-w-0 overflow-hidden' : 'bg-white border-gray-200 min-w-0 overflow-hidden';

  const isEs = lang === 'es';
  const label = (s: DocSection) => isEs ? s.labelEs : s.labelEn;

  return (
    <motion.div className={`h-full min-w-0 max-w-full overflow-hidden flex flex-col ${isDark ? 'bg-black' : 'bg-white'}`} initial={{opacity:0}} animate={{opacity:1}}>
      {/* Header */}
      <div className={`shrink-0 flex items-center gap-3 px-4 pt-[env(safe-area-inset-top,0px)] pb-3 border-b ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}>
        <button onClick={onBack} aria-label={t('docsBack')} className={`p-2 -ml-2 ${isDark ? 'text-white/60 hover:text-white' : 'text-gray-500 hover:text-gray-800'} active:scale-90 transition-transform`}>
          <MdArrowBack size={20} />
        </button>
        <img src="/logo-of-app.webp" alt="TrinaxAI" className="w-10 h-10 rounded-xl" width={40} height={40} />
        <span className={`text-sm font-medium ${isDark ? 'text-white/80' : 'text-gray-800'}`}>{t('docsTitle')}</span>
      </div>

      <div className="flex-1 flex min-h-0 min-w-0 max-w-full">
        {/* Sidebar */}
        <div className={`w-44 lg:w-52 shrink-0 overflow-y-auto border-r py-4 px-2 lg:px-3 hidden md:block ${sidebarBg}`}>
          <nav className="space-y-0.5">
            {sections.map((s) => (
              <button
                key={s.id}
                onClick={() => setActive(s.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-colors ${active === s.id ? activeLink : inactiveLink}`}
              >
                {label(s)}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="docs-content flex-1 w-full max-w-full md:max-w-3xl min-w-0 overflow-y-auto overflow-x-hidden px-3 sm:px-4 py-5 sm:py-6 pb-[calc(env(safe-area-inset-bottom,0px)+24px)] space-y-8 break-words [overflow-wrap:anywhere]">
          {/* Mobile section picker — dropdown */}
          <div className="md:hidden mb-4">
            <select
              value={active}
              onChange={(e) => setActive(e.target.value as Section)}
              aria-label={isEs ? 'Seleccionar seccion' : 'Select section'}
              className={`w-full px-3 py-2.5 rounded-xl border text-sm font-medium outline-none appearance-none ${isDark ? 'bg-white/[0.05] border-white/[0.1] text-white' : 'bg-white border-gray-300 text-gray-900'}`}
            >
              {sections.map((s) => (
                <option key={s.id} value={s.id}>{label(s)}</option>
              ))}
            </select>
          </div>

          {/* INTRO */}
          {active === 'intro' && (
            <div className="space-y-6">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? '¿Qué es TrinaxAI?' : 'What is TrinaxAI?'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg}`}>
                <p className={`text-sm leading-relaxed ${textSub}`}>
                  {isEs
                    ? 'TrinaxAI 1.1.0 es un asistente open-source bajo AGPL-3.0-or-later. La inferencia, RAG y datos persistidos funcionan localmente con Ollama; solo la búsqueda web opcional, las descargas y los destinos remotos que configures usan Internet.'
                    : 'TrinaxAI 1.1.0 is an open-source assistant under AGPL-3.0-or-later. Inference, RAG, and persisted data run locally with Ollama; only optional web search, downloads, and remote targets you configure use the Internet.'}
                </p>
              </div>

              {/* Architecture diagram */}
              <div className={`p-2 rounded-2xl border ${isDark ? 'border-white/[0.08] bg-white/[0.01]' : 'border-gray-300 bg-gray-50'} max-w-full overflow-x-auto`}>
                <pre className={`text-[10px] leading-tight font-mono ${isDark ? 'text-white/50' : 'text-gray-600'} p-3`}>{`┌──────────────────────────────────────────┐
│              Your Device                 │
│  ┌──────────┐  ┌─────────────────────┐   │
│  │PWA(React)│  │  CLI (trinaxai)     │   │
│  │  :3334   │  │  chat · agent · rag │   │
│  └─────┬─────┘  └──────────┬──────────┘   │
│        │                   │               │
│  ┌─────┴───────────────────┴──────────┐   │
│  │    RAG API (FastAPI) :3333         │   │
│  │ generation pipeline · LlamaIndex  │   │
│  │ bge-m3 · BM25 · rerank            │   │
│  └─────┬──────────────────────────────┘   │
│        │                                   │
│  ┌─────┴──────┐                            │
│  │   Ollama   │  qwen3.5 · qwen2.5-coder  │
│  │   :11434   │  bge-m3 · qwen3-vl        │
│  └────────────┘                            │
└──────────────────────────────────────────┘`}</pre>
              </div>

              <h2 className={`text-lg font-semibold ${textMain}`}>{isEs ? '¿Por qué TrinaxAI?' : 'Why TrinaxAI?'}</h2>
              <div className={`p-5 rounded-2xl border ${sectionBg}`}>
                <ul className={`text-sm space-y-2 ${textSub}`}>
                  <li>🔒 <strong className={textMain}>{isEs ? 'Privado por defecto' : 'Private by default'}</strong> — {isEs ? 'Chats, índice y memoria se quedan en el host; el modo Internet es explícito.' : 'Chats, index, and memory stay on the host; Internet mode is explicit.'}</li>
                  <li>💰 <strong className={textMain}>{isEs ? 'Gratis y Open Source' : 'Free & Open Source'}</strong> — {isEs ? 'Licencia AGPL-3.0-or-later. Sin costos ocultos, sin suscripciones.' : 'AGPL-3.0-or-later license. No hidden costs, no subscriptions.'}</li>
                  <li>⚡ <strong className={textMain}>{isEs ? 'Local' : 'Local'}</strong> — {isEs ? 'Sin viajes a una nube externa; la velocidad depende de tu hardware y del modelo.' : 'No external-cloud round trips; speed depends on your hardware and model.'}</li>
                  <li>🧠 <strong className={textMain}>{isEs ? 'Conoce tu código' : 'Knows your code'}</strong> — {isEs ? 'El RAG indexa tus proyectos. La IA responde con contexto real de tu trabajo.' : 'RAG indexes your projects. The AI responds with real context from your work.'}</li>
                  <li>🤖 <strong className={textMain}>{isEs ? 'Agente con herramientas' : 'Tool-using agent'}</strong> — {isEs ? 'Lee, escribe y ejecuta dentro de una carpeta autorizada.' : 'Reads, writes, and runs inside an authorized workspace.'}</li>
                  <li>🌍 <strong className={textMain}>{isEs ? 'Internet opcional' : 'Optional Internet'}</strong> — {isEs ? 'Búsqueda web e investigación con fuentes cuando tú las activas.' : 'Sourced web search and research when you enable them.'}</li>
                  <li>🌍 <strong className={textMain}>{isEs ? 'Multi-plataforma' : 'Cross-platform'}</strong> — Linux, macOS, Windows. PWA en iOS y Android.</li>
                </ul>
              </div>
            </div>
          )}

          {/* ABOUT */}
          {active === 'about' && (
            <div className="space-y-6">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Acerca de TrinaxAI' : 'About TrinaxAI'}</h1>

              <h2 className={`text-lg font-semibold ${textMain}`}>{isEs ? 'Por qué existe TrinaxAI' : 'Why TrinaxAI Exists'}</h2>
              <div className={`p-5 rounded-2xl border ${sectionBg}`}>
                <p className={`text-sm leading-relaxed ${textSub}`}>
                  {isEs
                    ? 'TrinaxAI nació de una convicción simple: la IA debe pertenecer a todos, no solo a las grandes tecnológicas. En un mundo donde los asistentes de IA exigen suscripciones a la nube, recolectan tus datos e imponen límites de uso, TrinaxAI toma el camino opuesto.'
                    : 'TrinaxAI was born from a simple conviction: AI should belong to everyone, not just big tech companies. In a world where AI assistants increasingly require cloud subscriptions, collect your data, and impose usage limits, TrinaxAI takes the opposite path.'}
                </p>
                <p className={`text-sm leading-relaxed mt-3 ${textSub}`}>
                  {isEs
                    ? 'Es un asistente de IA 100% local y de código abierto que se ejecuta completamente en tu máquina. Sin nube. Sin suscripciones. Sin límites. La visión es clara: ofrecer a desarrolladores, estudiantes y usuarios comunes la misma experiencia potente de IA que obtendrían de productos comerciales, pero con privacidad, libertad y control total.'
                    : 'It is a 100% local, open-source AI assistant that runs entirely on your machine. No cloud. No subscriptions. No limits. The vision is clear: give developers, students, and everyday users the same powerful AI experience they would get from commercial products, but with privacy, freedom, and full control.'}
                </p>
              </div>

              <h2 className={`text-lg font-semibold ${textMain}`}>{isEs ? 'Principios fundamentales' : 'Core Principles'}</h2>
              <div className={`p-5 rounded-2xl border ${sectionBg}`}>
                <ul className={`text-sm space-y-2 ${textSub}`}>
                  <li>🏠 <strong className={textMain}>{isEs ? 'Local-first' : 'Local-first'}</strong> — {isEs ? 'Todo se ejecuta en tu máquina a través de Ollama. Sin claves API.' : 'Everything runs on your machine via Ollama. No API keys required.'}</li>
                  <li>🔒 <strong className={textMain}>{isEs ? 'Privacidad' : 'Privacy-respecting'}</strong> — {isEs ? 'Tu código, tus chats, tus documentos se quedan contigo.' : 'Your code, your chats, your documents stay with you.'}</li>
                  <li>📖 <strong className={textMain}>{isEs ? 'Código abierto' : 'Open-source'}</strong> — AGPL-3.0-or-later. {isEs ? 'La comunidad puede auditar, bifurcar y mejorar.' : 'The community can audit, fork, and improve.'}</li>
                  <li>🚀 <strong className={textMain}>{isEs ? 'Calidad de producción' : 'Production-grade'}</strong> — {isEs ? 'Funciones reales: RAG con búsqueda híbrida, modo voz, visión, PWA, CLI.' : 'Real features: RAG with hybrid search, voice mode, vision, PWA, CLI.'}</li>
                  <li>🌐 <strong className={textMain}>{isEs ? 'Bilingüe por diseño' : 'Bilingual by design'}</strong> — {isEs ? 'Español e inglés, detectados automáticamente. Creado por un desarrollador latinoamericano para una audiencia global.' : 'Spanish and English, auto-detected. Built by a Latin American developer for a global audience.'}</li>
                </ul>
              </div>

              <h2 className={`text-lg font-semibold ${textMain}`}>{isEs ? 'El creador — TrinaxCode' : 'The Creator — TrinaxCode'}</h2>
              <div className={`p-5 rounded-2xl border ${sectionBg}`}>
                <p className={`text-sm leading-relaxed ${textSub}`}>
                  {isEs
                    ? 'TrinaxCode es un Full Stack Web Developer radicado en Tuxtla Gutiérrez, Chiapas, México, originario de Nicaragua. Su filosofía: "Impacto en producción, no demos de tutorial." No construye portafolios llenos de clones — construye productos que la gente realmente usa, que rankean en Google y resuelven problemas reales.'
                    : 'TrinaxCode is a Full Stack Web Developer based in Tuxtla Gutiérrez, Chiapas, México, originally from Nicaragua. His philosophy: "Production impact over tutorial demos." He doesn\'t build portfolios full of clones — he builds products people actually use, that rank on Google and solve real problems.'}
                </p>

                <h3 className={`text-sm font-semibold mt-4 ${textMain}`}>{isEs ? 'Trayectoria' : 'Background'}</h3>
                <ul className={`text-sm space-y-1.5 mt-2 ${textSub}`}>
                  <li>🎓 <strong>Harvard CS50x & CS50W</strong> — {isEs ? 'Certificado Profesional de Harvard en Programación Web.' : 'Harvard Professional Certificate in Web Programming.'}</li>
                  <li>🏫 <strong>Stanford Code in Place 2026</strong> — {isEs ? 'Participante seleccionado en la iniciativa internacional de Stanford.' : 'Selected participant in Stanford\'s international CS education initiative.'}</li>
                  <li>💻 <strong>Full Stack</strong> — React, TypeScript, Django, PostgreSQL, Firebase, Node.js.</li>
                  <li>📱 <strong>{isEs ? 'Creador de contenido' : 'Content creator'}</strong> — +60K {isEs ? 'seguidores en TikTok compartiendo conocimiento de programación en español.' : 'followers on TikTok sharing coding knowledge in Spanish.'}</li>
                </ul>

                <h3 className={`text-sm font-semibold mt-4 ${textMain}`}>{isEs ? 'Proyectos destacados' : 'Featured Projects'}</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                  {[
                    { name: 'Rednura Web', descEs: 'E-commerce de suplementos naturales. #1 en Tuxtla Gutiérrez.', descEn: 'Natural supplements e-commerce. #1 in Tuxtla Gutiérrez.' },
                    { name: 'Belcons Remodeling', descEs: 'Plataforma full-stack para empresa de remodelación en EE.UU.', descEn: 'Full-stack platform for a US remodeling company.' },
                    { name: 'CEDAS Montessori', descEs: 'Sitio institucional para escuela Montessori.', descEn: 'Institutional site for a Montessori school.' },
                    { name: 'Iglesia Adventista El Jobo', descEs: 'Portal comunitario con +10,000 visitas.', descEn: 'Community portal with +10,000 visits.' },
                  ].map((p) => (
                    <div key={p.name} className={`p-3 rounded-lg border ${sectionBg}`}>
                      <p className={`text-xs font-semibold ${textMain}`}>{p.name}</p>
                      <p className={`text-[11px] mt-1 ${textMuted}`}>{isEs ? p.descEs : p.descEn}</p>
                    </div>
                  ))}
                </div>

                <h3 className={`text-sm font-semibold mt-4 ${textMain}`}>{isEs ? 'Conecta' : 'Connect'}</h3>
                <div className="flex flex-wrap gap-2 mt-2">
                  {[
                    { label: 'GitHub', href: 'https://github.com/TrinaxCode' },
                    { label: 'LinkedIn', href: 'https://www.linkedin.com/in/trinaxcode/' },
                    { label: 'X', href: 'https://x.com/TrinaxCode' },
                    { label: 'Email', href: 'mailto:trinaxcode@gmail.com' },
                  ].map((link) => (
                    <a key={link.label} href={link.href} target="_blank" rel="noopener noreferrer"
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                        isDark
                          ? 'border-white/[0.08] text-white/60 hover:text-white hover:border-white/[0.15] hover:bg-white/[0.04]'
                          : 'border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      {link.label}
                    </a>
                  ))}
                </div>
              </div>

              <div className={`p-4 rounded-2xl border text-center ${isDark ? 'bg-[#006bbd]/10 border-[#006bbd]/20' : 'bg-[#006bbd]/5 border-[#006bbd]/20'}`}>
                <p className={`text-sm ${isDark ? 'text-[#006bbd]' : 'text-[#006bbd]'}`}>
                  {isEs
                    ? 'TrinaxAI está abierto a contribuidores, colaboradores y a cualquiera que crea que la IA debe ser libre, privada y local.'
                    : 'TrinaxAI is open to contributors, collaborators, and anyone who believes AI should be free, private, and local.'}
                </p>
              </div>
            </div>
          )}

          {/* INSTALL */}
          {active === 'install' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Instalación' : 'Installation'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                <h3 className={`font-semibold ${textMain}`}>🐧 Linux</h3>
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{isEs ? `# 1. Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Clonar TrinaxAI
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI

# 3. Ejecutar instalador automatico
chmod +x install.sh && ./install.sh

# 4. Activar entorno virtual
source .venv/bin/activate

# 5. Indexar tus proyectos
python index.py

# 6. Iniciar todo
./startup_ai.sh` : `# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Clone TrinaxAI
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI

# 3. Run auto-installer
chmod +x install.sh && ./install.sh

# 4. Activate virtual environment
source .venv/bin/activate

# 5. Index your projects
python index.py

# 6. Start everything
./startup_ai.sh`}</pre>
                <h3 className={`font-semibold ${textMain}`}>macOS</h3>
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{isEs ? `# 1. Instalar Ollama
brew install ollama

# 2-6. Igual que Linux` : `# 1. Install Ollama
brew install ollama

# 2-6. Same as Linux`}</pre>
                <h3 className={`font-semibold ${textMain}`}>Windows</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'Descarga Ollama desde ollama.com. Luego ejecuta el instalador PowerShell:'
                    : 'Download Ollama from ollama.com. Then run the PowerShell installer:'}
                </p>
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{isEs ? `# 1. Instalar Ollama (descarga desde ollama.com)
# 2. Ejecutar instalador de TrinaxAI
powershell -ExecutionPolicy Bypass -File .\\install.ps1

# 3. Activar entorno virtual
.venv\\Scripts\\activate

# 4. Indexar tus proyectos
python index.py

# 5. Iniciar todo
python service_manager.py start` : `# 1. Install Ollama (download from ollama.com)
# 2. Run TrinaxAI installer
powershell -ExecutionPolicy Bypass -File .\\install.ps1

# 3. Activate virtual environment
.venv\\Scripts\\activate

# 4. Index your projects
python index.py

# 5. Start everything
python service_manager.py start`}</pre>
                <p className={`text-xs ${textMuted}`}>
                  {isEs
                    ? 'También puedes usar WSL2 y seguir los mismos pasos de Linux. Git Bash con install.sh también funciona en Windows.'
                    : 'You can also use WSL2 and follow the same Linux steps. Git Bash with install.sh also works on Windows.'}
                </p>
                <div className={`p-3 rounded-lg text-xs ${isDark ? 'bg-[#006bbd]/10 text-[#006bbd]' : 'bg-[#006bbd]/5 text-[#006bbd]'}`}>
                  💡 <a href="https://www.canirun.ai" target="_blank" rel="noopener noreferrer" className="underline">canirun.ai</a>
                  {' '}{isEs ? '— descubre qué modelos puede ejecutar tu máquina antes de instalarlos.' : '— discover which models your machine can run before installing them.'}
                </div>
              </div>
            </div>
          )}

          {/* CONFIG */}
          {active === 'config' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Configuración' : 'Configuration'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'El archivo config.py contiene toda la configuración del sistema. Hay cuatro perfiles de hardware:'
                    : 'The config.py file contains all system configuration. There are four hardware profiles:'}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className={`p-3 rounded-lg border ${sectionBg}`}>
                    <p className={`font-semibold ${textMain}`}>8GB</p>
                    <p className={textMuted}>{isEs ? 'Equipos con poca RAM' : 'Low-RAM machines'}</p>
                    <ul className={`mt-2 space-y-1 ${textSub}`}>
                      <li>• num_ctx: 2048</li>
                      <li>• Embed workers: 1</li>
                      <li>• Reranker: OFF</li>
                      <li>• Keep alive: 0s</li>
                    </ul>
                  </div>
                  <div className={`p-3 rounded-lg border ${sectionBg}`}>
                    <p className={`font-semibold ${textMain}`}>16GB</p>
                    <p className={textMuted}>{isEs ? 'Perfil medio (por defecto)' : 'Default medium profile'}</p>
                    <ul className={`mt-2 space-y-1 ${textSub}`}>
                      <li>• num_ctx: 4096</li>
                      <li>• Embed workers: 2</li>
                      <li>• Reranker: OFF</li>
                      <li>• Keep alive: 0s</li>
                    </ul>
                  </div>
                  <div className={`p-3 rounded-lg border ${sectionBg}`}>
                    <p className={`font-semibold ${textMain}`}>Max / 32GB</p>
                    <p className={textMuted}>{isEs ? 'Equipos con buena RAM' : 'Machines with good RAM'}</p>
                    <ul className={`mt-2 space-y-1 ${textSub}`}>
                      <li>• num_ctx: 8192</li>
                      <li>• Embed workers: 4</li>
                      <li>• Reranker: optional</li>
                      <li>• Keep alive: 30m</li>
                    </ul>
                  </div>
                  <div className={`p-3 rounded-lg border ${sectionBg}`}>
                    <p className={`font-semibold ${textMain}`}>Ultra</p>
                    <p className={textMuted}>{isEs ? 'GPU potente + 32GB+ RAM' : 'Strong GPU + 32GB+ RAM'}</p>
                    <ul className={`mt-2 space-y-1 ${textSub}`}>
                      <li>• num_ctx: 16384</li>
                      <li>• Embed workers: 6</li>
                      <li>• Reranker: recommended</li>
                      <li>• Keep alive: 60m</li>
                    </ul>
                  </div>
                </div>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Variables de entorno' : 'Environment Variables'}</h3>
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{`TRINAXAI_CORS_ORIGINS=https://localhost:3334,https://YOUR-LAN-IP:3334
TRINAXAI_INDEX_DIR=~/Documents
TRINAXAI_PROFILE=ultra  # 8gb, 16gb, max, ultra
TRINAXAI_RAG_TARGET=http://localhost:3333
VITE_TRINAXAI_VISION_MODEL=qwen3-vl:4b-instruct`}</pre>
                <p className={`text-xs ${textMuted}`}>
                  {isEs
                    ? 'Ultra activa contexto 16K, más workers de embeddings y modelos profundos para máquinas con 32GB+ RAM y GPU potente. El reranker es opcional con requirements-rerank.txt.'
                    : 'Ultra enables 16K context, more embedding workers, and deeper models for machines with 32GB+ RAM and a strong GPU. Reranking is optional through requirements-rerank.txt.'}
                </p>
              </div>
            </div>
          )}

          {/* MODELS */}
          {active === 'models' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Modelos' : 'Models'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'TrinaxAI mantiene una flota Qwen especializada por rol y elige el modelo de texto correcto por turno. El pipeline de generación inteligente usa un clasificador determinista (sin llamada extra al modelo) para decidir modelo, parámetros y prompt.'
                    : 'TrinaxAI keeps a role-specific Qwen fleet and picks the right text model per turn. Its deterministic classifier (no extra model call) selects the model, decoding parameters, and prompt.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Ranuras de la flota (perfil 16GB)' : 'Fleet slots (16GB profile)'}</h3>
                <div className="max-w-full overflow-x-auto">
                  <table className={`w-full text-xs ${textSub}`}>
                    <thead>
                      <tr className={textMuted}>
                        <th className="text-left py-2">{isEs ? 'Ranura' : 'Slot'}</th>
                        <th className="text-left py-2">{isEs ? 'Se usa para' : 'Used for'}</th>
                        <th className="text-left py-2">{isEs ? 'Modelo' : 'Model'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr><td className="py-1.5">General</td><td className="py-1.5">{isEs ? 'Chat, razonamiento, matemáticas' : 'Chat, reasoning, math'}</td><td className="font-mono text-[#4ea3e0]">qwen3.5:9b</td></tr>
                      <tr><td className="py-1.5">Code</td><td className="py-1.5">{isEs ? 'Generación de código' : 'Code generation'}</td><td className="font-mono text-[#4ea3e0]">qwen2.5-coder:3b</td></tr>
                      <tr><td className="py-1.5">Deep</td><td className="py-1.5">{isEs ? 'Tareas complejas / multi-archivo' : 'Complex / multi-file tasks'}</td><td className="font-mono text-[#4ea3e0]">qwen3.5:9b</td></tr>
                      <tr><td className="py-1.5">Fast</td><td className="py-1.5">{isEs ? 'Preguntas muy cortas' : 'Very short prompts'}</td><td className="font-mono text-[#4ea3e0]">granite4:3b</td></tr>
                      <tr><td className="py-1.5">{isEs ? 'Visión' : 'Vision'}</td><td className="py-1.5">{isEs ? 'Análisis de imágenes' : 'Image analysis'}</td><td className="font-mono text-[#4ea3e0]">qwen3-vl:4b-instruct</td></tr>
                      <tr><td className="py-1.5">Embeddings</td><td className="py-1.5">{isEs ? 'Indexación / búsqueda' : 'Indexing / search'}</td><td className="font-mono text-[#4ea3e0]">bge-m3</td></tr>
                    </tbody>
                  </table>
                </div>
                <p className={`text-[11px] ${textMuted}`}>
                  {isEs
                    ? 'Perfiles: 8GB usa vision 2B; 16GB usa 4B; Max usa 8B; Ultra usa 30B-A3B MoE. Todo es sobrescribible en .env y vision se descarga al primer analisis de imagen.'
                    : 'Profiles: 8GB uses vision 2B; 16GB uses 4B; Max uses 8B; Ultra uses 30B-A3B MoE. Everything is overridable in .env and vision downloads on first image analysis.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Regímenes del pipeline' : 'Pipeline regimes'}</h3>
                <ul className={`text-sm space-y-1.5 ${textSub}`}>
                  <li>• <strong className={textMain}>Grounded-QA</strong> — {isEs ? 'responde solo desde el contexto RAG y cita las fuentes.' : 'answers only from RAG context and cites sources.'}</li>
                  <li>• <strong className={textMain}>Code</strong> — {isEs ? 'genera código con decodificación precisa.' : 'generates code with precise decoding.'}</li>
                  <li>• <strong className={textMain}>Reasoning</strong> — {isEs ? 'matemáticas/ciencia/algoritmos paso a paso, con LaTeX.' : 'step-by-step math/science/algorithms, with LaTeX.'}</li>
                  <li>• <strong className={textMain}>Creative</strong> — {isEs ? 'escritura y diseño con más temperatura.' : 'writing and design with higher temperature.'}</li>
                  <li>• <strong className={textMain}>Explain</strong> — {isEs ? 'explicaciones y preguntas generales.' : 'explanations and general questions.'}</li>
                </ul>
                <p className={`text-[11px] ${textMuted}`}>
                  {isEs
                    ? 'Tras generar, una validación determinista (sin LLM) revisa el código —parseo, delimitadores balanceados, marcadores esperados— y aplica un pase de corrección si hace falta.'
                    : 'After generating, a deterministic (no-LLM) validation checks the code — parsing, balanced delimiters, expected markers — and applies one correction pass if needed.'}
                </p>
              </div>
            </div>
          )}

          {/* INDEXING */}
          {active === 'indexing' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Indexación' : 'Indexing'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'index.py escanea tus proyectos y crea un índice de búsqueda semántica. La IA puede entonces buscar en tu código y responder con contexto real.'
                    : 'index.py scans your projects and creates a semantic search index. The AI can then search your code and respond with real context.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Características' : 'Features'}</h3>
                <ul className={`text-sm space-y-2 ${textSub}`}>
                  <li>• {isEs ? 'Indexación incremental: solo re-procesa archivos modificados' : 'Incremental indexing: only re-processes changed files'}</li>
                  <li>• {isEs ? 'Chunking AST-aware: respeta la estructura del código' : 'AST-aware chunking: respects code structure'}</li>
                  <li>• {isEs ? 'Búsqueda híbrida: vectorial + BM25 para máxima relevancia' : 'Hybrid search: vector + BM25 for maximum relevance'}</li>
                  <li>• {isEs ? 'Soporta 18+ lenguajes de programación' : 'Supports 18+ programming languages'}</li>
                  <li>• {isEs ? 'Re-ranker opcional para resultados más precisos' : 'Optional re-ranker for more accurate results'}</li>
                </ul>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Uso' : 'Usage'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'Desde Configuración puedes elegir una carpeta con el explorador de archivos, asignarla a una colección y luego indexarla. El navegador no revela la ruta original por seguridad, así que TrinaxAI copia los archivos al backend local y luego indexa esa copia.'
                    : 'From Settings you can choose a folder using the file picker, assign it to a collection, and index it. Browsers do not reveal the original absolute path for security, so TrinaxAI copies the files into the local backend and indexes that copy.'}
                </p>
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{isEs ? `# Indexacion completa
python index.py

# Recargar el indice en la API
curl -X POST http://localhost:3333/system/reload

# TrinaxAI CLI interactivo
trinaxai chat --engine rag` : `# Full indexing
python index.py

# Reload index in the API
curl -X POST http://localhost:3333/system/reload

# Interactive TrinaxAI CLI
trinaxai chat --engine rag`}</pre>
                <p className={`text-xs ${textMuted}`}>
                  {isEs
                    ? 'Instala la CLI desde la raíz con pip install -e . y usa trinaxai chat para consultas interactivas.'
                    : 'Install the CLI from the repository root with pip install -e . and use trinaxai chat for interactive queries.'}
                </p>
              </div>
            </div>
          )}

          {/* AGENT */}
          {active === 'agent' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Agente' : 'Agent'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'El Agente de TrinaxAI es un asistente programador con herramientas, 100% local y privado. Trabaja dentro de una carpeta (workspace) que tú eliges y ejecuta un bucle de razonamiento + uso de herramientas hasta terminar la tarea.'
                    : "TrinaxAI's Agent is a private, local tool-using coding assistant. It works inside a workspace folder you choose and runs a reasoning + tool-use loop until the task is done."}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Herramientas (en sandbox)' : 'Tools (sandboxed)'}</h3>
                <ul className={`text-sm space-y-1.5 ${textSub}`}>
                  <li>📖 <code className="font-mono text-[#4ea3e0]">read_file</code> · <code className="font-mono text-[#4ea3e0]">list_dir</code> · <code className="font-mono text-[#4ea3e0]">glob</code> · <code className="font-mono text-[#4ea3e0]">grep</code> — {isEs ? 'exploran y leen archivos.' : 'explore and read files.'}</li>
                  <li>✏️ <code className="font-mono text-[#4ea3e0]">write_file</code> · <code className="font-mono text-[#4ea3e0]">edit_file</code> — {isEs ? 'crean y modifican archivos (piden confirmación).' : 'create and modify files (ask for approval).'}</li>
                  <li>⚙️ <code className="font-mono text-[#4ea3e0]">run_command</code> — {isEs ? 'ejecuta comandos en un sandbox sin red (pide confirmación).' : 'runs commands in a networkless sandbox (asks for approval).'}</li>
                </ul>
                <div className={`p-3 rounded-lg text-xs ${isDark ? 'bg-[#006bbd]/10 text-[#006bbd]' : 'bg-[#006bbd]/5 text-[#006bbd]'}`}>
                  🔒 {isEs
                    ? 'Todas las herramientas están confinadas al workspace: se rechazan rutas con ".." o symlinks que escapen. Las acciones peligrosas (escribir, editar, ejecutar) requieren tu aprobación salvo que uses el modo yolo explícitamente.'
                    : 'All tools are confined to the workspace: paths with ".." or escaping symlinks are rejected. Dangerous actions (write, edit, run) require your approval unless you explicitly enable yolo mode.'}
                </div>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Cómo usarlo' : 'How to use it'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'En la PWA, abre la vista de Agente y elige una carpeta de trabajo. Desde la terminal, usa la CLI:'
                    : 'In the PWA, open the Agent view and pick a working folder. From the terminal, use the CLI:'}
                </p>
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{isEs ? `# Agente interactivo en la carpeta actual
trinaxai agent --workspace .

# Una sola tarea y salir
trinaxai agent --prompt "añade tests al modulo utils"

# Sin confirmaciones (solo en carpetas de confianza)
trinaxai agent --yolo` : `# Interactive agent in the current folder
trinaxai agent --workspace .

# Run a single task and exit
trinaxai agent --prompt "add tests to the utils module"

# No approval prompts (trusted folders only)
trinaxai agent --yolo`}</pre>
                <p className={`text-xs ${textMuted}`}>
                  {isEs
                    ? 'El mismo motor impulsa la CLI y el endpoint /v1/agent de la API. Requiere un modelo con soporte de herramientas (la flota Qwen lo tiene).'
                    : 'The same engine powers the CLI and the API /v1/agent endpoint. It requires a tool-capable model (the Qwen fleet supports this).'}
                </p>
              </div>
            </div>
          )}

          {/* INTERNET AND RESEARCH */}
          {active === 'research' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Internet e investigación' : 'Internet and research'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'El chat normal y RAG no necesitan Internet. Activa el modo Internet cuando necesites noticias, versiones, documentación o datos actuales; TrinaxAI indicará las fuentes usadas.'
                    : 'Normal chat and RAG do not need the Internet. Enable Internet mode for news, versions, documentation, or current facts; TrinaxAI identifies the sources it used.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Proveedores' : 'Providers'}</h3>
                <ul className={`text-sm space-y-1.5 ${textSub}`}>
                  <li><strong className={textMain}>DuckDuckGo</strong> — {isEs ? 'funciona sin clave.' : 'works without an API key.'}</li>
                  <li><strong className={textMain}>Brave Search</strong> — {isEs ? 'se usa al configurar TRINAXAI_BRAVE_SEARCH_API_KEY.' : 'used when TRINAXAI_BRAVE_SEARCH_API_KEY is configured.'}</li>
                  <li><strong className={textMain}>SearXNG</strong> — {isEs ? 'permite usar tu propia instancia.' : 'supports your self-hosted instance.'}</li>
                </ul>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Investigación profunda' : 'Deep research'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'Descompone la pregunta en varias búsquedas, puede combinar fuentes web con colecciones RAG autorizadas y entrega una síntesis citada. La profundidad se limita de 1 a 3 pasadas.'
                    : 'It decomposes a question into several searches, can combine web sources with authorized RAG collections, and returns a cited synthesis. Depth is bounded from 1 to 3 passes.'}
                </p>
                <div className={`p-3 rounded-lg text-xs ${isDark ? 'bg-amber-500/10 text-amber-300' : 'bg-amber-50 text-amber-800'}`}>
                  {isEs
                    ? 'Privacidad: las consultas del modo Internet se envían al proveedor elegido. TrinaxAI bloquea destinos locales/privados al leer páginas y limita tamaño, redirecciones y tiempo.'
                    : 'Privacy: Internet-mode queries are sent to the selected provider. TrinaxAI blocks local/private page targets and limits size, redirects, and time.'}
                </div>
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{isEs ? `# CLI
trinaxai research --query "compara las versiones actuales" --depth 2` : `# CLI
trinaxai research --query "compare the current versions" --depth 2`}</pre>
              </div>
            </div>
          )}

          {/* FILES */}
          {active === 'files' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Archivos y colecciones' : 'Files and collections'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Archivos adjuntos' : 'Attached files'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'Adjuntar un archivo en el chat no lo guarda ni lo indexa automáticamente. TrinaxAI lee el contenido como contexto temporal para analizarlo en esa conversación. Si el modo RAG está activo, verás una opción separada para indexarlo y elegir la colección.'
                    : 'Attaching a file in chat does not save or index it automatically. TrinaxAI reads it as temporary context for that conversation. If RAG mode is active, you will see a separate option to index it and choose the collection.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Colecciones' : 'Collections'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'Las colecciones son espacios de conocimiento. Puedes crear, renombrar y borrar colecciones desde Configuración; luego activar una o varias en el chat RAG.'
                    : 'Collections are knowledge spaces. You can create, rename, and delete them from Settings, then activate one or more in RAG chat.'}
                </p>
              </div>
            </div>
          )}

          {/* SECURITY */}
          {active === 'security' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Modelo de Seguridad' : 'Security Model'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                {[
                  {
                    titleEs: 'Local-first',
                    titleEn: 'Local-first',
                    bodyEs: 'TrinaxAI ejecuta Ollama, RAG, colecciones e historial en tu equipo o red local. No necesita un servicio cloud para funcionar.',
                    bodyEn: 'TrinaxAI runs Ollama, RAG, collections, and history on your computer or local network. It does not need a cloud service to work.',
                  },
                  {
                    titleEs: 'Acciones protegidas',
                    titleEn: 'Protected actions',
                    bodyEs: 'Apagar/encender servicios, recargar índices, importar carpetas desde navegador, sincronizar estado y modificar colecciones pasan por autorización localhost/LAN o token.',
                    bodyEn: 'Starting/stopping services, reloading indexes, browser folder imports, app-state sync, and collection changes use localhost/LAN or token authorization.',
                  },
                  {
                    titleEs: 'Protección LAN',
                    titleEn: 'LAN protection',
                    bodyEs: 'Por defecto las acciones sensibles aceptan localhost. Los teléfonos/tablets pueden abrir la PWA en la misma WiFi, pero el control de sistema por LAN requiere activación explícita.',
                    bodyEn: 'By default sensitive actions accept localhost. Phones/tablets can open the PWA on the same WiFi, but LAN system control requires explicit opt-in.',
                  },
                  {
                    titleEs: 'Protección con token',
                    titleEn: 'Token protection',
                    bodyEs: 'Si expones TrinaxAI fuera de tu red privada, configura TRINAXAI_ADMIN_TOKEN y TRINAXAI_ALLOW_LAN_SYSTEM=0. Para acceso remoto, usa VPN.',
                    bodyEn: 'If you expose TrinaxAI outside your private network, set TRINAXAI_ADMIN_TOKEN and TRINAXAI_ALLOW_LAN_SYSTEM=0. For remote access, use a VPN.',
                  },
                  {
                    titleEs: 'Configuración segura recomendada',
                    titleEn: 'Recommended safe setup',
                    bodyEs: 'Mantén TrinaxAI en localhost o WiFi privada, no abras puertos a internet y usa VPN si necesitas acceso remoto.',
                    bodyEn: 'Keep TrinaxAI on localhost or private WiFi, do not expose ports to the internet, and use a VPN if you need remote access.',
                  },
                ].map((item) => (
                  <div key={item.titleEn} className={`p-3 rounded-lg border ${sectionBg}`}>
                    <h3 className={`text-sm font-semibold ${textMain}`}>{isEs ? item.titleEs : item.titleEn}</h3>
                    <p className={`mt-1 text-xs leading-relaxed ${textSub}`}>{isEs ? item.bodyEs : item.bodyEn}</p>
                  </div>
                ))}
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{`TRINAXAI_ALLOW_LAN_SYSTEM=1
TRINAXAI_ADMIN_TOKEN=<strong-random-token>`}</pre>
              </div>
            </div>
          )}

          {/* API */}
          {active === 'api' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{t('docsApiReference')}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                {[
                  { method: 'GET', path: '/health', descEs: 'Estado del sistema: modelos, índice, proyectos', descEn: 'System status: models, index, projects' },
                  { method: 'GET', path: '/resources', descEs: 'Telemetría local básica de RAM/VRAM', descEn: 'Basic local RAM/VRAM telemetry' },
                  { method: 'POST', path: '/v1/chat/completions', descEs: 'Chat RAG con streaming SSE (OpenAI-compatible)', descEn: 'RAG chat with SSE streaming (OpenAI-compatible)' },
                  { method: 'POST', path: '/v1/agent', descEs: 'Agente con herramientas (SSE); /v1/agent/approve y /v1/agent/browse', descEn: 'Tool-using agent (SSE); plus /v1/agent/approve and /v1/agent/browse' },
                  { method: 'POST', path: '/v1/research', descEs: 'Investigación profunda multipaso', descEn: 'Multi-pass deep research' },
                  { method: 'GET', path: '/v1/memory', descEs: 'Memoria local (GET/POST/PATCH/DELETE, context, summary)', descEn: 'Local memory (GET/POST/PATCH/DELETE, context, summary)' },
                  { method: 'GET', path: '/v1/sources', descEs: 'Listar/borrar fuentes indexadas y ver sus chunks', descEn: 'List/delete indexed sources and view their chunks' },
                  { method: 'POST', path: '/v1/watch/start', descEs: 'Vigilante de archivos (start/stop/status)', descEn: 'File watcher (start/stop/status)' },
                  { method: 'POST', path: '/v1/pairing/claim', descEs: 'Emparejar un dispositivo LAN con un código de un uso', descEn: 'Pair a LAN device with a one-time code' },
                  { method: 'POST', path: '/v1/voice/stt', descEs: 'Voz-a-texto y /v1/voice/tts texto-a-voz', descEn: 'Speech-to-text, plus /v1/voice/tts text-to-speech' },
                  { method: 'GET', path: '/collections', descEs: 'Listar/crear/editar/borrar colecciones RAG', descEn: 'List/create/edit/delete RAG collections' },
                  { method: 'POST', path: '/documents/extract', descEs: 'Extraer texto de un documento (PDF/Office/…)', descEn: 'Extract text from a document (PDF/Office/…)' },
                  { method: 'GET', path: '/v1/stats', descEs: 'Estadísticas de uso; /v1/usage registra eventos', descEn: 'Usage statistics; /v1/usage records events' },
                  { method: 'POST', path: '/system/reload', descEs: 'Recargar índice; también shutdown/startup/index-upload', descEn: 'Reload index; also shutdown/startup/index-upload' },
                  { method: 'GET', path: '/app-state', descEs: 'Estado compartido entre dispositivos (GET/PUT/DELETE)', descEn: 'Cross-device shared state (GET/PUT/DELETE)' },
                ].map((ep) => (
                  <div key={ep.path} className={`p-3 rounded-lg border ${sectionBg}`}>
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${ep.method === 'GET' ? 'bg-green-500/20 text-green-400' : 'bg-[#006bbd]/20 text-[#006bbd]'}`}>{ep.method}</span>
                      <code className={`text-xs font-mono break-all ${textMain}`}>{ep.path}</code>
                    </div>
                    <p className={`text-xs mt-1 ${textSub}`}>{isEs ? ep.descEs : ep.descEn}</p>
                  </div>
                ))}
                <h3 className={`font-semibold ${textMain}`}>{t('docsSseStreamFormat')}</h3>
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{`data: {"trinaxai":{"model":"qwen3.5:4b","project":"Insider"}}
data: {"choices":[{"delta":{"content":"Hello!"}}]}
data: {"trinaxai_sources":[{"file":"app.py","snippet":"..."}]}
data: [DONE]`}</pre>
                <p className={`text-[11px] ${textMuted}`}>
                  {isEs
                    ? 'La API se sirve en :3333. La PWA la alcanza vía el proxy del mismo origen /api/rag/*. Los endpoints privados requieren un dispositivo emparejado o acceso local. Especificación completa: /openapi.json.'
                    : 'The API is served on :3333. The PWA reaches it via the same-origin /api/rag/* proxy. Private endpoints require a paired device or local access. Full spec: /openapi.json.'}
                </p>
              </div>
            </div>
          )}

          {/* PWA */}
          {active === 'pwa' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{t('docsPwaGuide')}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'TrinaxAI es una Progressive Web App. Puedes instalarla como una app nativa en cualquier dispositivo.'
                    : 'TrinaxAI is a Progressive Web App. You can install it as a native app on any device.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{t('docsIosSafari')}</h3>
                <ol className={`text-sm space-y-1 ${textSub} list-decimal pl-4`}>
                  <li>{isEs ? 'Abre Safari y navega a https://[TU_IP]:3334' : 'Open Safari and go to https://[YOUR_IP]:3334'}</li>
                  <li>{isEs ? 'Toca el botón Compartir (📤)' : 'Tap the Share button (📤)'}</li>
                  <li>{isEs ? 'Selecciona "Añadir a la pantalla de inicio"' : 'Select "Add to Home Screen"'}</li>
                  <li>{isEs ? 'Toca "Añadir"' : 'Tap "Add"'}</li>
                </ol>
                <h3 className={`font-semibold ${textMain}`}>{t('docsAndroidChrome')}</h3>
                <ol className={`text-sm space-y-1 ${textSub} list-decimal pl-4`}>
                  <li>{isEs ? 'Abre Chrome y navega a https://[TU_IP]:3334' : 'Open Chrome and go to https://[YOUR_IP]:3334'}</li>
                  <li>{isEs ? 'Toca los 3 puntos ⋮ → "Instalar aplicación"' : 'Tap 3 dots ⋮ → "Install app"'}</li>
                </ol>
                <h3 className={`font-semibold ${textMain}`}>{t('docsDesktop')}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'Chrome/Edge: icono de instalación en la barra de direcciones.'
                    : 'Chrome/Edge: install icon in the address bar.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Conectar otro dispositivo' : 'Connect another device'}</h3>
                <ol className={`text-sm space-y-1 ${textSub} list-decimal pl-4`}>
                  <li>{isEs ? 'Asegúrate de que ambos equipos estén en la misma red privada' : 'Make sure both devices are on the same private network'}</li>
                  <li>{isEs ? 'Encuentra tu IP local: ip addr show | grep 192.168' : 'Find your local IP: ip addr show | grep 192.168'}</li>
                  <li>{isEs ? 'En la PWA host abre Configuración → Dispositivo emparejado → Generar código' : 'In the host PWA open Settings → Paired device → Generate pairing code'}</li>
                  <li>{isEs ? 'Abre https://[TU_IP_LOCAL]:3334 en el otro equipo, elige la instalación existente e introduce el código' : 'Open https://[YOUR_LOCAL_IP]:3334 on the other device, choose the existing installation, and enter the code'}</li>
                  <li>{isEs ? 'Si no conecta, permite el puerto 3334 del gateway; FastAPI y Ollama deben seguir en loopback' : 'If it does not connect, allow gateway port 3334; FastAPI and Ollama should remain on loopback'}</li>
                </ol>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'La red sólo permite llegar al chat básico. RAG, historial, memoria, archivos, indexación, agente y acciones del sistema requieren emparejamiento y scopes explícitos. El host concede chat/read_private por defecto y debe autorizar index, agent o system sólo cuando hagan falta.'
                    : 'Network access only reaches basic chat. RAG, history, memory, files, indexing, the agent, and system actions require pairing and explicit scopes. The host grants chat/read_private by default and should authorize index, agent, or system only when needed.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Certificado HTTPS local' : 'Local HTTPS certificate'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'El instalador crea un certificado local para HTTPS e intenta confiarlo en la computadora host. En teléfonos o tablets, el sistema no puede confiarlo automáticamente: importa el certificado local en ese dispositivo o usa un dominio/VPN con certificado público si necesitas que el navegador no muestre advertencias.'
                    : 'The installer creates a local HTTPS certificate and attempts to trust it on the host computer. Phones and tablets cannot trust that certificate automatically: import the local certificate on that device, or use a domain/VPN with a public certificate if you need the browser to show no warnings.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Móviles y tablets' : 'Phones and tablets'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'La interfaz usa el visual viewport del navegador para que el input permanezca visible cuando aparece el teclado. Si un navegador viejo no soporta esa API, TrinaxAI conserva un fallback con altura dinámica.'
                    : 'The interface uses the browser visual viewport so the input stays visible when the keyboard opens. If an older browser does not support that API, TrinaxAI keeps a dynamic-height fallback.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Sincronización local' : 'Local sync'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'La PWA sincroniza configuración, modelos, onboarding e historial con el backend local de TrinaxAI. Si abres la app desde otro teléfono o navegador en la misma máquina/red, recupera esos datos sin repetir la configuración inicial.'
                    : 'The PWA syncs settings, models, onboarding, and chat history with the local TrinaxAI backend. When you open the app from another phone or browser on the same machine/network, it restores those details without repeating setup.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Acciones del sistema' : 'System actions'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'Apagar IA y Encender IA se ejecutan en el servidor que hospeda TrinaxAI. Desde el teléfono no necesitas mandar el token manualmente; el servidor local se encarga de ejecutar los scripts configurados.'
                    : 'Shutdown AI and Start AI run on the server hosting TrinaxAI. From a phone you do not need to send the token manually; the local server runs the configured scripts.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Imágenes' : 'Images'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'Las imágenes se reducen antes de enviarse al modelo de visión para evitar respuestas lentas y consumo excesivo de memoria. En 16GB se usa qwen3-vl:4b-instruct por defecto; si no está instalado, TrinaxAI lo descarga al primer análisis de imagen.'
                    : 'Images are resized before being sent to the vision model to avoid slow responses and excessive memory use. On 16GB, qwen3-vl:4b-instruct is the default; if it is not installed, TrinaxAI downloads it on first image analysis.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{t('docsContinue')}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'TrinaxAI incluye un archivo continue-config.yaml para la extensión Continue.dev en VSCode y forks (Cursor, Windsurf, etc.). Cópialo a ~/.continue/config.yaml y podrás usar TrinaxAI directamente desde tu editor.'
                    : 'TrinaxAI includes a continue-config.yaml file for the Continue.dev extension in VSCode and forks (Cursor, Windsurf, etc.). Copy it to ~/.continue/config.yaml and you can use TrinaxAI directly from your editor.'}
                </p>
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{isEs ? `# Copia la configuracion
cp continue-config.yaml ~/.continue/config.yaml

# Reinicia VSCode
# Los modelos de TrinaxAI apareceran en el selector de Continue` : `# Copy the config
cp continue-config.yaml ~/.continue/config.yaml

# Restart VSCode
# TrinaxAI models will appear in Continue's model picker`}</pre>
                <p className={`text-xs ${textMuted}`}>
                  {isEs
                    ? 'La configuración incluye RAG Local compatible con OpenAI en http://localhost:3333/v1, modelos Ollama para chat/edit/apply/autocomplete y bge-m3 para embeddings.'
                    : 'The config includes OpenAI-compatible Local RAG at http://localhost:3333/v1, Ollama models for chat/edit/apply/autocomplete, and bge-m3 embeddings.'}
                </p>
              </div>
            </div>
          )}

          {/* TROUBLESHOOT */}
          {active === 'troubleshoot' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Solución de problemas' : 'Troubleshooting'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                {[
                  { qEs: 'Ollama no responde', qEn: 'Ollama not responding', aEs: 'Abre Configuración y pulsa Encender IA, o ejecuta ./startup_ai.sh desde la carpeta de TrinaxAI. También puedes revisar el estado con python service_manager.py status.', aEn: 'Open Settings and press Start AI, or run ./startup_ai.sh from the TrinaxAI folder. You can also check status with python service_manager.py status.' },
                  { qEs: 'La PWA no conecta desde el teléfono', qEn: 'PWA won\'t connect from phone', aEs: 'Permite el puerto 3334 del gateway en la red privada. Mantén 3333 y 11434 bloqueados y usa https://.', aEn: 'Allow gateway port 3334 on the private network. Keep 3333 and 11434 blocked and use https://.' },
                  { qEs: 'La indexación dice que no conecta al backend', qEn: 'Indexing says it cannot connect to the backend', aEs: 'Abre Configuración y pulsa Encender IA. Si usas el teléfono, abre la URL de red que muestra Vite, por ejemplo https://TU_IP:3334 o 3335. El backend RAG debe estar accesible desde la máquina host.', aEn: 'Open Settings and press Start AI. If you are on a phone, open the network URL shown by Vite, for example https://YOUR_IP:3334 or 3335. The RAG backend must be reachable from the host machine.' },
                  { qEs: 'Apagar IA o Encender IA no funciona', qEn: 'Shutdown AI or Start AI does not work', aEs: 'Estas acciones se ejecutan en la máquina que hospeda TrinaxAI. Verifica que service_manager.py, startup_ai.sh y shutdown_ai.sh existan y que la PWA se esté sirviendo desde el instalador de TrinaxAI.', aEn: 'These actions run on the machine hosting TrinaxAI. Check that service_manager.py, startup_ai.sh, and shutdown_ai.sh exist and that the PWA is being served by the TrinaxAI installer.' },
                  { qEs: 'La configuración no aparece en otro dispositivo', qEn: 'Settings do not appear on another device', aEs: 'Los dispositivos deben abrir la misma instancia de TrinaxAI y poder acceder a la API RAG. La sincronización es local, no cloud: se guarda en storage/app_state.json del host.', aEn: 'Devices must open the same TrinaxAI instance and reach the RAG API. Sync is local, not cloud: it is stored in storage/app_state.json on the host.' },
                  { qEs: 'Error "model not found"', qEn: '"model not found" error', aEs: 'El modelo no está descargado. Ejecuta: ollama pull [nombre-del-modelo]. Visita ollama.com/library para ver modelos disponibles.', aEn: 'The model isn\'t downloaded. Run: ollama pull [model-name]. Visit ollama.com/library to see available models.' },
                  { qEs: 'La indexación es muy lenta', qEn: 'Indexing is too slow', aEs: 'Mantén TRINAXAI_EMBED_KEEP_ALIVE en 15m o 30m para no recargar el embedder entre lotes. Usa TRINAXAI_EMBED_BATCH=8 en 16GB, baja EMBED_WORKERS/BATCH solo si falta RAM y excluye node_modules/.git.', aEn: 'Keep TRINAXAI_EMBED_KEEP_ALIVE at 15m or 30m so the embedder is not reloaded between batches. Use TRINAXAI_EMBED_BATCH=8 on 16GB, lower EMBED_WORKERS/BATCH only if RAM is tight, and exclude node_modules/.git.' },
                  { qEs: 'Mucho uso de RAM', qEn: 'High RAM usage', aEs: 'Usa el perfil 16GB en config.py. Baja num_ctx a 2048. Usa modelos más pequeños (1.5b en vez de 7b). Cierra otras aplicaciones.', aEn: 'Use the 16GB profile in config.py. Lower num_ctx to 2048. Use smaller models (1.5b instead of 7b). Close other applications.' },
                ].map((item, i) => (
                  <details key={i} className={`p-3 rounded-lg border ${sectionBg}`}>
                    <summary className={`text-sm font-medium cursor-pointer ${textMain}`}>{isEs ? item.qEs : item.qEn}</summary>
                    <p className={`text-xs mt-2 ${textSub}`}>{isEs ? item.aEs : item.aEn}</p>
                  </details>
                ))}
              </div>
            </div>
          )}

          {/* CONTRIBUTING */}
          {active === 'contributing' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>{isEs ? 'Contribuir' : 'Contributing'}</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? '¡TrinaxAI es open source (AGPL-3.0-or-later)! Cualquier contribución es bienvenida. Así puedes ayudar:'
                    : 'TrinaxAI is open source (AGPL-3.0-or-later)! All contributions are welcome. Here\'s how you can help:'}
                </p>
                <ul className={`text-sm space-y-2 ${textSub}`}>
                  <li>🐛 {isEs ? 'Reporta bugs en GitHub Issues' : 'Report bugs on GitHub Issues'}</li>
                  <li>💡 {isEs ? 'Sugiere nuevas funcionalidades' : 'Suggest new features'}</li>
                  <li>📝 {isEs ? 'Mejora la documentación' : 'Improve documentation'}</li>
                  <li>🌍 {isEs ? 'Traduce a más idiomas' : 'Translate to more languages'}</li>
                  <li>🔧 {isEs ? 'Envía Pull Requests con mejoras' : 'Submit Pull Requests with improvements'}</li>
                </ul>
                <div className={`p-3 rounded-lg text-xs ${isDark ? 'bg-[#006bbd]/10 text-[#006bbd]' : 'bg-[#006bbd]/5 text-[#006bbd]'}`}>
                  ⭐ {isEs ? '¿Te gusta el proyecto? ¡Deja una estrella en GitHub! Ayudarías muchísimo.' : 'Like the project? Leave a star on GitHub! It helps a lot.'}
                  <br />
                  <a href="https://github.com/TrinaxCode/TrinaxAI" target="_blank" rel="noopener noreferrer" className="underline mt-1 inline-block">
                    github.com/TrinaxCode/TrinaxAI
                  </a>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
