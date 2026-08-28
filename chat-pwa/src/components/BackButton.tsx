import type { Ref } from 'react';
import { MdArrowBack } from 'react-icons/md';

interface Props {
  onClick: () => void;
  label: string;
  isDark: boolean;
  buttonRef?: Ref<HTMLButtonElement>;
  className?: string;
}

export default function BackButton({ onClick, label, isDark, buttonRef, className = '' }: Props) {
  const tone = isDark ? 'text-white/60 hover:bg-white/[0.06] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800';

  return (
    <button
      ref={buttonRef}
      type="button"
      onClick={onClick}
      aria-label={label}
      className={`inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-xl p-2 transition-[background-color,color,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-95 ${tone} ${className}`}
    >
      <MdArrowBack size={20} aria-hidden="true" />
    </button>
  );
}
