import { MdWarningAmber } from 'react-icons/md';

import { useI18n } from '../i18n/I18nContext';
import {
  BASE_DEVICE_SCOPES,
  ELEVATED_DEVICE_SCOPES,
  GRANTABLE_DEVICE_SCOPES,
  type DeviceScope,
} from '../lib/authHeaders';

interface Props {
  legend: string;
  value: readonly string[];
  onChange: (scopes: DeviceScope[]) => void;
  isDark: boolean;
  disabled?: boolean;
}

/** Checklist of the permissions the host can grant to one paired device. */
export default function DeviceScopePicker({ legend, value, onChange, isDark, disabled = false }: Props) {
  const { t } = useI18n();
  const border = isDark ? 'border-white/[0.08]' : 'border-gray-200';
  const muted = isDark ? 'text-white/65' : 'text-gray-600';
  const text = isDark ? 'text-white/85' : 'text-gray-800';
  const warn = isDark ? 'text-amber-300' : 'text-amber-800';

  const toggle = (scope: DeviceScope, checked: boolean) => {
    onChange(GRANTABLE_DEVICE_SCOPES.filter((item) => (item === scope ? checked : value.includes(item))));
  };

  const group = (title: string, scopes: readonly DeviceScope[], elevated: boolean) => (
    <div className="space-y-1.5">
      <p className={`flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider ${elevated ? warn : muted}`}>
        {elevated && <MdWarningAmber size={14} aria-hidden="true" />}
        {title}
      </p>
      {scopes.map((scope) => {
        const checked = value.includes(scope);
        return (
          <label
            key={scope}
            className={`flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border px-3 py-2 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[#4aa7ed] ${
              checked && elevated
                ? (isDark ? 'border-amber-300/40 bg-amber-300/[0.06]' : 'border-amber-400 bg-amber-50')
                : border
            } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
          >
            <input
              type="checkbox"
              name={`device-scope-${scope}`}
              checked={checked}
              disabled={disabled}
              onChange={(event) => toggle(scope, event.target.checked)}
              className="mt-1 h-4 w-4 shrink-0 accent-[#006bbd]"
            />
            <span className="min-w-0">
              <span className={`block text-sm font-medium ${text}`}>{t(`deviceScope_${scope}`)}</span>
              <span className={`block text-sm leading-relaxed ${muted}`}>{t(`deviceScopeDesc_${scope}`)}</span>
            </span>
          </label>
        );
      })}
    </div>
  );

  return (
    <fieldset disabled={disabled} className="min-w-0 space-y-3">
      <legend className={`mb-2 text-sm font-semibold ${text}`}>{legend}</legend>
      {group(t('devicePermissionsBasic'), BASE_DEVICE_SCOPES, false)}
      {group(t('devicePermissionsElevated'), ELEVATED_DEVICE_SCOPES, true)}
      <p className={`text-sm leading-relaxed ${muted}`}>{t('devicePermissionsHostOnly')}</p>
    </fieldset>
  );
}
