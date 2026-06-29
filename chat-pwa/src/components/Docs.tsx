import { useState } from 'react';
import { motion } from 'framer-motion';
import { MdArrowBack } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';

interface Props { onBack: () => void; }

type Section = 'intro' | 'install' | 'config' | 'models' | 'indexing' | 'files' | 'security' | 'api' | 'pwa' | 'troubleshoot' | 'contributing';

interface DocSection {
  id: Section;
  labelEs: string;
  labelEn: string;
  icon: string;
}

const sections: DocSection[] = [
  { id: 'intro', labelEs: 'Introduccion', labelEn: 'Introduction', icon: '' },
  { id: 'install', labelEs: 'Instalacion', labelEn: 'Installation', icon: '' },
  { id: 'config', labelEs: 'Configuracion', labelEn: 'Configuration', icon: '' },
  { id: 'models', labelEs: 'Modelos', labelEn: 'Models', icon: '' },
  { id: 'indexing', labelEs: 'Indexacion', labelEn: 'Indexing', icon: '' },
  { id: 'files', labelEs: 'Archivos', labelEn: 'Files', icon: '' },
  { id: 'security', labelEs: 'Seguridad', labelEn: 'Security', icon: '' },
  { id: 'api', labelEs: 'API Reference', labelEn: 'API Reference', icon: '' },
  { id: 'pwa', labelEs: 'Guia PWA', labelEn: 'PWA Guide', icon: '' },
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
        <button onClick={onBack} aria-label={isEs ? 'Volver' : 'Go back'} className={`p-2 -ml-2 ${isDark ? 'text-white/60 hover:text-white' : 'text-gray-500 hover:text-gray-800'} active:scale-90 transition-transform`}>
          <MdArrowBack size={20} />
        </button>
        <img src="/logo-of-app.webp" alt="TrinaxAI" className="w-10 h-10 rounded-xl" />
        <span className={`text-sm font-medium ${isDark ? 'text-white/80' : 'text-gray-800'}`}>{isEs ? 'Documentacion' : 'Documentation'}</span>
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
                    ? 'TrinaxAI es un asistente de inteligencia artificial 100% local, open-source y diseñado para ser increíblemente fácil de usar. Corre completamente en tu máquina usando Ollama para modelos de lenguaje y un sistema RAG (Retrieval-Augmented Generation) que indexa tus proyectos. Sin nube, sin suscripciones, sin límites. Todo privado.'
                    : 'TrinaxAI is a 100% local, open-source AI assistant designed to be incredibly easy to use. It runs entirely on your machine using Ollama for language models and a custom RAG (Retrieval-Augmented Generation) system that indexes your projects. No cloud, no subscriptions, no limits. Completely private.'}
                </p>
              </div>

              {/* Architecture diagram */}
              <div className={`p-2 rounded-2xl border ${isDark ? 'border-white/[0.08] bg-white/[0.01]' : 'border-gray-300 bg-gray-50'} max-w-full overflow-x-auto`}>
                <pre className={`text-[10px] leading-tight font-mono ${isDark ? 'text-white/50' : 'text-gray-600'} p-3`}>{`┌──────────────────────────────────────────┐
│              Your Device                 │
│  ┌──────────┐  ┌─────────────────────┐   │
│  │PWA(React)│  │ VSCode (Continue)   │   │
│  │  :3334   │  │ continue-config.yaml│   │
│  └─────┬─────┘  └──────────┬──────────┘   │
│        │                   │               │
│  ┌─────┴───────────────────┴──────────┐   │
│  │    RAG API (FastAPI) :3333         │   │
│  │ LlamaIndex · bge-m3 · BM25        │   │
│  └─────┬──────────────────────────────┘   │
│        │                                   │
│  ┌─────┴──────┐                            │
│  │   Ollama   │  qwen2.5 · llama3.2       │
│  │   :11434   │  bge-m3 · moondream       │
│  └────────────┘                            │
└──────────────────────────────────────────┘`}</pre>
              </div>

              <h2 className={`text-lg font-semibold ${textMain}`}>{isEs ? '¿Por qué TrinaxAI?' : 'Why TrinaxAI?'}</h2>
              <div className={`p-5 rounded-2xl border ${sectionBg}`}>
                <ul className={`text-sm space-y-2 ${textSub}`}>
                  <li>🔒 <strong className={textMain}>{isEs ? '100% Privado' : '100% Private'}</strong> — {isEs ? 'Tus datos nunca salen de tu máquina. No se envía nada a servidores externos.' : 'Your data never leaves your machine. Nothing is sent to external servers.'}</li>
                  <li>💰 <strong className={textMain}>{isEs ? 'Gratis y Open Source' : 'Free & Open Source'}</strong> — {isEs ? 'Licencia AGPL-3.0-or-later. Sin costos ocultos, sin suscripciones.' : 'AGPL-3.0-or-later license. No hidden costs, no subscriptions.'}</li>
                  <li>⚡ <strong className={textMain}>{isEs ? 'Rápido' : 'Fast'}</strong> — {isEs ? 'Respuestas en milisegundos. Sin latencia de red.' : 'Responses in milliseconds. No network latency.'}</li>
                  <li>🧠 <strong className={textMain}>{isEs ? 'Conoce tu código' : 'Knows your code'}</strong> — {isEs ? 'El RAG indexa tus proyectos. La IA responde con contexto real de tu trabajo.' : 'RAG indexes your projects. The AI responds with real context from your work.'}</li>
                  <li>🌍 <strong className={textMain}>{isEs ? 'Multi-plataforma' : 'Cross-platform'}</strong> — Linux, macOS, Windows. PWA en iOS y Android.</li>
                </ul>
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
TRINAXAI_PROFILE=ultra  # low, medium, high, ultra
VITE_TRINAXAI_RAG_TARGET=https://localhost:3333
VITE_TRINAXAI_VISION_MODEL=qwen2.5vl:3b
VITE_TRINAXAI_VISION_QUALITY_MODEL=qwen2.5vl:7b`}</pre>
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
                    ? 'TrinaxAI usa un sistema de auto-enrutamiento que selecciona el mejor modelo según tu consulta:'
                    : 'TrinaxAI uses an auto-routing system that selects the best model based on your query:'}
                </p>
                <div className="max-w-full overflow-x-auto">
                  <table className={`w-full text-xs ${textSub}`}>
                    <thead>
                      <tr className={textMuted}>
                        <th className="text-left py-2">{isEs ? 'Condición' : 'Condition'}</th>
                        <th className="text-left py-2">{isEs ? 'Modelo' : 'Model'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr><td className="py-1.5">{isEs ? 'Complejo / +600 chars' : 'Complex / >600 chars'}</td><td className="font-mono text-[#4ea3e0]">qwen2.5-coder:7b *</td></tr>
                      <tr><td className="py-1.5">{isEs ? 'Código detectado' : 'Code detected'}</td><td className="font-mono text-[#4ea3e0]">qwen2.5-coder:3b</td></tr>
                      <tr><td className="py-1.5">{isEs ? 'Chat general' : 'General chat'}</td><td className="font-mono text-[#4ea3e0]">llama3.2:3b</td></tr>
                      <tr><td className="py-1.5">{isEs ? 'Trivial (-25 chars)' : 'Trivial (&lt;25 chars)'}</td><td className="font-mono text-[#4ea3e0]">llama3.2:3b</td></tr>
                      <tr><td className="py-1.5">{isEs ? 'Visión (rápido)' : 'Vision (fast)'}</td><td className="font-mono text-[#4ea3e0]">qwen2.5vl:3b</td></tr>
                      <tr><td className="py-1.5">{isEs ? 'Visión (calidad)' : 'Vision (quality)'}</td><td className="font-mono text-[#4ea3e0]">qwen2.5vl:7b</td></tr>
                      <tr><td className="py-1.5">{isEs ? 'Embeddings' : 'Embeddings'}</td><td className="font-mono text-[#4ea3e0]">bge-m3</td></tr>
                    </tbody>
                  </table>
                </div>
                <p className={`text-[11px] ${textMuted}`}>* {isEs ? 'En perfil Ultra: qwen2.5-coder:14b. En perfil bajo (8gb): qwen2.5-coder:3b.' : 'On Ultra profile: qwen2.5-coder:14b. On low profile (8gb): qwen2.5-coder:3b.'}</p>
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
curl -k -X POST https://localhost:3333/system/reload

# TrinaxAI CLI interactivo
python trinaxai_cli.py --engine rag` : `# Full indexing
python index.py

# Reload index in the API
curl -k -X POST https://localhost:3333/system/reload

# Interactive TrinaxAI CLI
python trinaxai_cli.py --engine rag`}</pre>
                <p className={`text-xs ${textMuted}`}>
                  {isEs
                    ? 'query.py sigue existiendo como wrapper compatible, pero el nombre nuevo es TrinaxAI CLI: trinaxai_cli.py.'
                    : 'query.py still exists as a compatible wrapper, but the new name is TrinaxAI CLI: trinaxai_cli.py.'}
                </p>
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
                    bodyEs: 'Por defecto acepta localhost y clientes de LAN privada confiable para que la PWA funcione desde teléfono/tablet en la misma WiFi.',
                    bodyEn: 'By default it accepts localhost and trusted private LAN clients so the PWA works from phones/tablets on the same WiFi.',
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
TRINAXAI_ADMIN_TOKEN=`}</pre>
              </div>
            </div>
          )}

          {/* API */}
          {active === 'api' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>API Reference</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                {[
                  { method: 'GET', path: '/health', descEs: 'Estado del sistema: modelos, índice, proyectos', descEn: 'System status: models, index, projects' },
                  { method: 'POST', path: '/v1/chat/completions', descEs: 'Chat RAG con streaming SSE (OpenAI-compatible)', descEn: 'RAG chat with SSE streaming (OpenAI-compatible)' },
                  { method: 'POST', path: '/system/shutdown', descEs: 'Apagar Ollama + RAG API (requiere auth)', descEn: 'Shutdown Ollama + RAG API (requires auth)' },
                  { method: 'POST', path: '/system/startup', descEs: 'Encender Ollama + RAG API y mantener la PWA disponible', descEn: 'Start Ollama + RAG API and keep the PWA available' },
                  { method: 'POST', path: '/system/reload', descEs: 'Recargar índice después de index.py', descEn: 'Reload index after index.py' },
                  { method: 'POST', path: '/system/index-upload', descEs: 'Importar carpeta elegida en navegador e indexarla', descEn: 'Import a browser-selected folder and index it' },
                  { method: 'GET', path: '/collections', descEs: 'Listar colecciones RAG', descEn: 'List RAG collections' },
                  { method: 'POST', path: '/collections', descEs: 'Crear colección RAG', descEn: 'Create RAG collection' },
                  { method: 'GET', path: '/resources', descEs: 'Telemetría local básica de RAM/VRAM', descEn: 'Basic local RAM/VRAM telemetry' },
                  { method: 'GET', path: '/app-state', descEs: 'Leer configuración e historial compartidos entre dispositivos', descEn: 'Read shared settings and chat history across devices' },
                  { method: 'PUT', path: '/app-state', descEs: 'Guardar configuración e historial compartidos localmente', descEn: 'Save shared local settings and chat history' },
                  { method: 'DELETE', path: '/app-state', descEs: 'Restaurar configuración compartida del host', descEn: 'Reset shared host configuration' },
                ].map((ep) => (
                  <div key={ep.path} className={`p-3 rounded-lg border ${sectionBg}`}>
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${ep.method === 'GET' ? 'bg-green-500/20 text-green-400' : 'bg-[#006bbd]/20 text-[#006bbd]'}`}>{ep.method}</span>
                      <code className={`text-xs font-mono break-all ${textMain}`}>{ep.path}</code>
                    </div>
                    <p className={`text-xs mt-1 ${textSub}`}>{isEs ? ep.descEs : ep.descEn}</p>
                  </div>
                ))}
                <h3 className={`font-semibold ${textMain}`}>SSE Stream Format</h3>
                <pre className={`text-xs font-mono p-3 rounded-lg ${codeBg}`}>{`data: {"trinaxai":{"model":"qwen2.5-coder:3b","project":"Insider"}}
data: {"choices":[{"delta":{"content":"Hello!"}}]}
data: {"trinaxai_sources":[{"file":"app.py","snippet":"..."}]}
data: [DONE]`}</pre>
              </div>
            </div>
          )}

          {/* PWA */}
          {active === 'pwa' && (
            <div className="space-y-5">
              <h1 className={`text-2xl font-bold ${textMain}`}>PWA Guide</h1>
              <div className={`p-5 rounded-2xl border ${sectionBg} space-y-4`}>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'TrinaxAI es una Progressive Web App. Puedes instalarla como una app nativa en cualquier dispositivo.'
                    : 'TrinaxAI is a Progressive Web App. You can install it as a native app on any device.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>📱 iOS (Safari)</h3>
                <ol className={`text-sm space-y-1 ${textSub} list-decimal pl-4`}>
                  <li>{isEs ? 'Abre Safari y navega a https://[TU_IP]:3334' : 'Open Safari and go to https://[YOUR_IP]:3334'}</li>
                  <li>{isEs ? 'Toca el botón Compartir (📤)' : 'Tap the Share button (📤)'}</li>
                  <li>{isEs ? 'Selecciona "Añadir a la pantalla de inicio"' : 'Select "Add to Home Screen"'}</li>
                  <li>{isEs ? 'Toca "Añadir"' : 'Tap "Add"'}</li>
                </ol>
                <h3 className={`font-semibold ${textMain}`}>🤖 Android (Chrome)</h3>
                <ol className={`text-sm space-y-1 ${textSub} list-decimal pl-4`}>
                  <li>{isEs ? 'Abre Chrome y navega a https://[TU_IP]:3334' : 'Open Chrome and go to https://[YOUR_IP]:3334'}</li>
                  <li>{isEs ? 'Toca los 3 puntos ⋮ → "Instalar aplicación"' : 'Tap 3 dots ⋮ → "Install app"'}</li>
                </ol>
                <h3 className={`font-semibold ${textMain}`}>💻 Desktop</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'Chrome/Edge: icono de instalación en la barra de direcciones.'
                    : 'Chrome/Edge: install icon in the address bar.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Conectar desde el teléfono' : 'Connect from your phone'}</h3>
                <ol className={`text-sm space-y-1 ${textSub} list-decimal pl-4`}>
                  <li>{isEs ? 'Asegúrate de que el teléfono esté en la misma red WiFi' : 'Make sure your phone is on the same WiFi network'}</li>
                  <li>{isEs ? 'Encuentra tu IP local: ip addr show | grep 192.168' : 'Find your local IP: ip addr show | grep 192.168'}</li>
                  <li>{isEs ? 'Abre https://[TU_IP_LOCAL]:3334 en el navegador del teléfono' : 'Open https://[YOUR_LOCAL_IP]:3334 in your phone browser'}</li>
                  <li>{isEs ? 'Si no conecta, verifica el firewall (puertos 3333, 3334, 11434)' : 'If it doesn\'t connect, check your firewall (ports 3333, 3334, 11434)'}</li>
                </ol>
                <h3 className={`font-semibold ${textMain}`}>{isEs ? 'Certificado autofirmado' : 'Self-signed certificate'}</h3>
                <p className={`text-sm ${textSub}`}>
                  {isEs
                    ? 'Como TrinaxAI usa HTTPS con certificado autofirmado, tu navegador mostrará una advertencia de seguridad. Haz clic en "Opciones avanzadas" o "Advanced" y selecciona "Continuar de todos modos" o "Proceed anyway". Esto es seguro — la conexión está encriptada, solo que el certificado no está firmado por una autoridad externa.'
                    : 'Since TrinaxAI uses HTTPS with a self-signed certificate, your browser will show a security warning. Click "Advanced" or "Advanced options" and select "Proceed anyway" or "Continue to site". This is safe — the connection is encrypted, the certificate just isn\'t signed by an external authority.'}
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
                    ? 'Las imágenes se reducen antes de enviarse al modelo de visión para evitar respuestas lentas y consumo excesivo de memoria. El modelo rápido se usa por defecto; pide “máxima calidad” solo cuando necesites más detalle.'
                    : 'Images are resized before being sent to the vision model to avoid slow responses and excessive memory use. The fast model is used by default; ask for “maximum quality” only when you need more detail.'}
                </p>
                <h3 className={`font-semibold ${textMain}`}>🔧 Continue.dev (VSCode)</h3>
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
                    ? 'La configuración incluye RAG Local compatible con OpenAI en https://localhost:3333/v1, modelos Ollama para chat/edit/apply/autocomplete y bge-m3 para embeddings.'
                    : 'The config includes OpenAI-compatible Local RAG at https://localhost:3333/v1, Ollama models for chat/edit/apply/autocomplete, and bge-m3 embeddings.'}
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
                  { qEs: 'La PWA no conecta desde el teléfono', qEn: 'PWA won\'t connect from phone', aEs: 'Verifica que el firewall permita los puertos 3333, 3334, 11434. En Linux: sudo ufw allow 3334/tcp. Asegúrate de usar https:// (no http).', aEn: 'Check firewall allows ports 3333, 3334, 11434. On Linux: sudo ufw allow 3334/tcp. Make sure to use https:// (not http).' },
                  { qEs: 'La indexación dice que no conecta al backend', qEn: 'Indexing says it cannot connect to the backend', aEs: 'Abre Configuración y pulsa Encender IA. Si usas el teléfono, abre la URL de red que muestra Vite, por ejemplo https://TU_IP:3334 o 3335. El backend RAG debe estar accesible desde la máquina host.', aEn: 'Open Settings and press Start AI. If you are on a phone, open the network URL shown by Vite, for example https://YOUR_IP:3334 or 3335. The RAG backend must be reachable from the host machine.' },
                  { qEs: 'Apagar IA o Encender IA no funciona', qEn: 'Shutdown AI or Start AI does not work', aEs: 'Estas acciones se ejecutan en la máquina que hospeda TrinaxAI. Verifica que service_manager.py, startup_ai.sh y shutdown_ai.sh existan y que la PWA se esté sirviendo desde el instalador de TrinaxAI.', aEn: 'These actions run on the machine hosting TrinaxAI. Check that service_manager.py, startup_ai.sh, and shutdown_ai.sh exist and that the PWA is being served by the TrinaxAI installer.' },
                  { qEs: 'La configuración no aparece en otro dispositivo', qEn: 'Settings do not appear on another device', aEs: 'Los dispositivos deben abrir la misma instancia de TrinaxAI y poder acceder a la API RAG. La sincronización es local, no cloud: se guarda en storage/app_state.json del host.', aEn: 'Devices must open the same TrinaxAI instance and reach the RAG API. Sync is local, not cloud: it is stored in storage/app_state.json on the host.' },
                  { qEs: 'Error "model not found"', qEn: '"model not found" error', aEs: 'El modelo no está descargado. Ejecuta: ollama pull [nombre-del-modelo]. Visita ollama.com/library para ver modelos disponibles.', aEn: 'The model isn\'t downloaded. Run: ollama pull [model-name]. Visit ollama.com/library to see available models.' },
                  { qEs: 'La indexación es muy lenta', qEn: 'Indexing is too slow', aEs: 'Reduce EMBED_WORKERS en config.py. Excluye node_modules y .git en PROJECTS_DIRS. Usa el modo incremental para solo procesar cambios.', aEn: 'Reduce EMBED_WORKERS in config.py. Exclude node_modules and .git from PROJECTS_DIRS. Use incremental mode to only process changes.' },
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
