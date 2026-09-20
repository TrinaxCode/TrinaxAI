import type { ReactNode } from 'react';

export interface IconProps {
  size?: number;
  strokeWidth?: number;
  className?: string;
}

function IconBase({ children, size = 18, strokeWidth = 1.8, className }: IconProps & { children: ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      focusable="false"
      height={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={strokeWidth}
      viewBox="0 0 24 24"
      width={size}
    >
      {children}
    </svg>
  );
}

export function IconGrid(props: IconProps) {
  return <IconBase {...props}><rect height="7" rx="1.5" width="7" x="3" y="3" /><rect height="7" rx="1.5" width="7" x="14" y="3" /><rect height="7" rx="1.5" width="7" x="3" y="14" /><rect height="7" rx="1.5" width="7" x="14" y="14" /></IconBase>;
}

export function IconMessage(props: IconProps) {
  return <IconBase {...props}><path d="M20 11.2a7.5 7.5 0 0 1-8 7.3 8.8 8.8 0 0 1-3.1-.6L4 20l1.7-3.7A7.2 7.2 0 0 1 4 11.2 7.5 7.5 0 0 1 12 4a7.5 7.5 0 0 1 8 7.2Z" /><path d="M8 11.5h.01M12 11.5h.01M16 11.5h.01" /></IconBase>;
}

export function IconBook(props: IconProps) {
  return <IconBase {...props}><path d="M4.5 5.5A2.5 2.5 0 0 1 7 3h11.5v16H7a2.5 2.5 0 0 0-2.5 2.5v-16Z" /><path d="M4.5 19.5A2.5 2.5 0 0 1 7 17h11.5M8 7h7M8 10h5" /></IconBase>;
}

export function IconBot(props: IconProps) {
  return <IconBase {...props}><rect height="12" rx="3" width="15" x="4.5" y="7" /><path d="M12 3v4M8 12h.01M16 12h.01M8.5 16h7" /><path d="M2.5 11v4M21.5 11v4" /></IconBase>;
}

export function IconDatabase(props: IconProps) {
  return <IconBase {...props}><ellipse cx="12" cy="5.5" rx="7.5" ry="3" /><path d="M4.5 5.5v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6M4.5 11.5v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6" /></IconBase>;
}

export function IconSettings(props: IconProps) {
  return <IconBase {...props}><path d="M12 8.8a3.2 3.2 0 1 0 0 6.4 3.2 3.2 0 0 0 0-6.4Z" /><path d="m19.4 13.2 1.1.8-1.8 3-1.3-.5a7.4 7.4 0 0 1-1.8 1l-.2 1.4h-3.5l-.2-1.4a7.4 7.4 0 0 1-1.8-1l-1.3.5-1.8-3 1.1-.8a6.7 6.7 0 0 1 0-2.4l-1.1-.8 1.8-3 1.3.5a7.4 7.4 0 0 1 1.8-1L12 5.1h3.5l.2 1.4a7.4 7.4 0 0 1 1.8 1l1.3-.5 1.8 3-1.1.8a6.7 6.7 0 0 1-.1 2.4Z" /></IconBase>;
}

export function IconSearch(props: IconProps) {
  return <IconBase {...props}><circle cx="10.8" cy="10.8" r="6.3" /><path d="m16 16 4.5 4.5" /></IconBase>;
}

export function IconPlus(props: IconProps) {
  return <IconBase {...props}><path d="M12 5v14M5 12h14" /></IconBase>;
}

export function IconChevronDown(props: IconProps) {
  return <IconBase {...props}><path d="m6 9 6 6 6-6" /></IconBase>;
}

export function IconChevronRight(props: IconProps) {
  return <IconBase {...props}><path d="m9 6 6 6-6 6" /></IconBase>;
}

export function IconMenu(props: IconProps) {
  return <IconBase {...props}><path d="M4 7h16M4 12h16M4 17h16" /></IconBase>;
}

export function IconX(props: IconProps) {
  return <IconBase {...props}><path d="m6 6 12 12M18 6 6 18" /></IconBase>;
}

export function IconSpark(props: IconProps) {
  return <IconBase {...props}><path d="m12 3 1.3 5.7L19 10l-5.7 1.3L12 17l-1.3-5.7L5 10l5.7-1.3L12 3ZM19 16l.6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6L19 16Z" /></IconBase>;
}

export function IconShield(props: IconProps) {
  return <IconBase {...props}><path d="M12 3.5 19 6v5.2c0 4.3-2.6 7.6-7 9.3-4.4-1.7-7-5-7-9.3V6l7-2.5Z" /><path d="m8.5 12 2.2 2.2 4.8-4.8" /></IconBase>;
}

export function IconFolder(props: IconProps) {
  return <IconBase {...props}><path d="M3.5 7.5A2.5 2.5 0 0 1 6 5h3l1.7 2h7.3a2.5 2.5 0 0 1 2.5 2.5v7A2.5 2.5 0 0 1 18 19H6a2.5 2.5 0 0 1-2.5-2.5v-9Z" /></IconBase>;
}

export function IconArrowUp(props: IconProps) {
  return <IconBase {...props}><path d="M12 19V5M6.5 10.5 12 5l5.5 5.5" /></IconBase>;
}

export function IconPaperclip(props: IconProps) {
  return <IconBase {...props}><path d="m8.5 12.5 6.2-6.2a3.2 3.2 0 0 1 4.5 4.5l-7.8 7.8a4.7 4.7 0 0 1-6.7-6.7l7.4-7.4a2.8 2.8 0 1 1 4 4l-7.1 7.1a1 1 0 0 0 1.4 1.4l6.6-6.6" /></IconBase>;
}

export function IconMic(props: IconProps) {
  return <IconBase {...props}><rect height="10" rx="4" width="6" x="9" y="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7" /></IconBase>;
}

export function IconSun(props: IconProps) {
  return <IconBase {...props}><circle cx="12" cy="12" r="3.5" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></IconBase>;
}

export function IconMoon(props: IconProps) {
  return <IconBase {...props}><path d="M19.5 15.5A7.5 7.5 0 0 1 8.5 4.4 7.8 7.8 0 1 0 19.5 15.5Z" /></IconBase>;
}

export function IconCheck(props: IconProps) {
  return <IconBase {...props}><path d="m5 12.5 4.3 4.3L19 7" /></IconBase>;
}

export function IconRotate(props: IconProps) {
  return <IconBase {...props}><path d="M20 11a8 8 0 0 0-14.6-4L4 9" /><path d="M4 4v5h5M4 13a8 8 0 0 0 14.6 4L20 15" /><path d="M20 20v-5h-5" /></IconBase>;
}

export function IconExternal(props: IconProps) {
  return <IconBase {...props}><path d="M14 5h5v5M19 5l-8 8" /><path d="M18 13v4.5A1.5 1.5 0 0 1 16.5 19h-9A1.5 1.5 0 0 1 6 17.5v-9A1.5 1.5 0 0 1 7.5 7H12" /></IconBase>;
}

export function IconCommand(props: IconProps) {
  return <IconBase {...props}><path d="M8 8V6a3 3 0 1 0-3 3h2M16 8V6a3 3 0 1 1 3 3h-2M8 16v2a3 3 0 1 1-3-3h2M16 16v2a3 3 0 1 0 3-3h-2M8 8h8v8H8z" /></IconBase>;
}

export function IconClock(props: IconProps) {
  return <IconBase {...props}><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.5 2" /></IconBase>;
}

export function IconActivity(props: IconProps) {
  return <IconBase {...props}><path d="M3 12h4l2.2-5 4.1 10 2.1-5H21" /></IconBase>;
}

export function IconCode(props: IconProps) {
  return <IconBase {...props}><path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 5l-4 14" /></IconBase>;
}

export function IconFile(props: IconProps) {
  return <IconBase {...props}><path d="M6.5 3.5h7l4 4v13h-11v-17Z" /><path d="M13.5 3.5v4h4M9 12h6M9 15h6" /></IconBase>;
}

export function IconGlobe(props: IconProps) {
  return <IconBase {...props}><circle cx="12" cy="12" r="8.5" /><path d="M3.8 9h16.4M3.8 15h16.4M12 3.5c2.1 2.3 3.1 5.1 3.1 8.5s-1 6.2-3.1 8.5c-2.1-2.3-3.1-5.1-3.1-8.5s1-6.2 3.1-8.5Z" /></IconBase>;
}

export function IconLock(props: IconProps) {
  return <IconBase {...props}><rect height="9" rx="2" width="13" x="5.5" y="10" /><path d="M8.5 10V7a3.5 3.5 0 0 1 7 0v3" /></IconBase>;
}

export function IconMore(props: IconProps) {
  return <IconBase {...props}><circle cx="5" cy="12" fill="currentColor" r="1" stroke="none" /><circle cx="12" cy="12" fill="currentColor" r="1" stroke="none" /><circle cx="19" cy="12" fill="currentColor" r="1" stroke="none" /></IconBase>;
}

export function IconPlay(props: IconProps) {
  return <IconBase {...props}><path d="m8 5 11 7-11 7V5Z" /></IconBase>;
}

export function IconAlert(props: IconProps) {
  return <IconBase {...props}><path d="m12 3 9 17H3L12 3Z" /><path d="M12 9v4M12 16h.01" /></IconBase>;
}

export function IconPanel(props: IconProps) {
  return <IconBase {...props}><rect height="17" rx="2" width="18" x="3" y="3.5" /><path d="M8 4v16M12 8h5M12 12h5M12 16h3" /></IconBase>;
}

export function IconSliders(props: IconProps) {
  return <IconBase {...props}><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="9" cy="6" fill="currentColor" r="1.5" stroke="none" /><circle cx="15" cy="12" fill="currentColor" r="1.5" stroke="none" /><circle cx="10" cy="18" fill="currentColor" r="1.5" stroke="none" /></IconBase>;
}

export function IconServer(props: IconProps) {
  return <IconBase {...props}><rect height="6" rx="1.5" width="17" x="3.5" y="4" /><rect height="6" rx="1.5" width="17" x="3.5" y="14" /><path d="M7 7h.01M7 17h.01M11 7h5M11 17h5" /></IconBase>;
}
