import { MdBolt } from 'react-icons/md';
import type { Translate } from '../chat/types';
import { isLocalHostBrowser } from '../../lib/authHeaders';

interface AgentYoloSwitchProps {
  enabled: boolean;
  disabled: boolean;
  onChange: (enabled: boolean) => void;
  isDark: boolean;
  t: Translate;
  /** Full-width row for the phone tools menu. */
  mobile?: boolean;
}

/** YOLO is a safety-relevant switch, so its state is carried by colour, icon and a real toggle. */
export default function AgentYoloSwitch({ enabled, disabled, onChange, isDark, t, mobile = false }: AgentYoloSwitchProps) {
  // Auto-approve is host-only: a paired device keeps confirming every dangerous action.
  if (!isLocalHostBrowser()) return null;
  const tone = enabled
    ? isDark ? 'border-red-400/45 bg-red-500/15 text-red-200 hover:bg-red-500/25' : 'border-red-300 bg-red-50 text-red-700 hover:bg-red-100'
    : isDark ? 'border-white/[0.1] text-white/70 hover:bg-white/[0.06] hover:text-white' : 'border-gray-200 text-gray-600 hover:bg-gray-100 hover:text-gray-800';
  const track = enabled ? 'bg-red-500' : isDark ? 'bg-white/20' : 'bg-gray-300';

  return (
    <button
      type="button"
      role="switch"
      data-yolo-switch={mobile ? 'mobile' : 'header'}
      data-enabled={enabled ? 'true' : 'false'}
      aria-checked={enabled}
      aria-label={enabled ? t('agentYoloModeOn') : t('agentYoloModeOff')}
      title={enabled ? t('agentYoloModeOn') : t('agentYoloModeOff')}
      onClick={() => onChange(!enabled)}
      disabled={disabled}
      className={`${mobile ? 'w-full gap-2.5 rounded-lg px-2.5 text-left' : 'gap-2 rounded-xl px-2.5'} flex min-h-11 items-center border text-xs font-bold uppercase tracking-wider transition-[background-color,border-color,color,transform] active:scale-[0.97] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-red-500/70 disabled:opacity-40 ${mobile ? 'border-transparent' : ''} ${mobile && !enabled ? isDark ? 'text-white/75 hover:bg-white/[0.06]' : 'text-gray-700 hover:bg-gray-100' : tone}`}
    >
      <MdBolt size={17} aria-hidden="true" className={`shrink-0 ${enabled ? 'motion-safe:animate-pulse' : ''}`} />
      <span className="min-w-0 flex-1">
        <span className="block">{t('agentYoloMode')}</span>
        {mobile && <span className={`block text-[11px] font-normal normal-case tracking-normal ${isDark ? 'text-white/60' : 'text-gray-600'}`}>{t('agentYoloHint')}</span>}
      </span>
      <span aria-hidden="true" className={`relative h-4 w-7 shrink-0 rounded-full transition-colors ${track}`}>
        <span className={`absolute left-0.5 top-0.5 h-3 w-3 rounded-full bg-white shadow-sm transition-transform ${enabled ? 'translate-x-3' : ''}`} />
      </span>
    </button>
  );
}
