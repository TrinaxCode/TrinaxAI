import type { TranslationKey } from '../../i18n/translations';

export type ActivityKind = 'thinking' | 'image' | 'web';

const ACTIVITY_KEYS = {
  thinking: [
    'thinking',
    'activityThinkingPrepare',
    'activityThinkingConnect',
    'activityThinkingWork',
    'activityThinkingReflect',
    'activityThinkingCompose',
    'activityThinkingOrganize',
    'activityThinkingReview',
    'activityThinkingFocus',
    'activityThinkingSolve',
    'activityThinkingExplore',
    'activityThinkingReason',
    'activityThinkingRefine',
    'activityThinkingCheck',
    'activityThinkingBuild',
    'activityThinkingShape',
  ],
  image: [
    'activityImageAnalyze',
    'activityImageCreation',
    'activityImageDetails',
    'activityImageInterpret',
    'activityImageObserve',
    'activityImageColors',
    'activityImageComposition',
    'activityImageElements',
    'activityImageScene',
    'activityImageVisual',
    'activityImageContext',
    'activityImagePatterns',
    'activityImageFocus',
    'activityImageCompare',
    'activityImageUnderstand',
    'activityImageTexture',
    'activityImageLight',
    'activityImageStory',
    'activityImageReview',
    'activityImageCloser',
  ],
  web: [
    'webSearching',
    'activityWebSources',
    'activityWebExplore',
    'activityWebVerify',
    'activityWebResults',
    'activityWebCrossCheck',
    'activityWebLatest',
    'activityWebCompare',
    'activityWebPrimary',
    'activityWebEvidence',
    'activityWebReading',
    'activityWebConfirm',
    'activityWebNavigate',
    'activityWebFactCheck',
    'activityWebDiscover',
    'activityWebCurrent',
  ],
} as const satisfies Record<ActivityKind, readonly TranslationKey[]>;

export function pickActivityMessage(
  kind: ActivityKind,
  translate: (key: TranslationKey) => string,
  previous = '',
  random: () => number = Math.random,
): string {
  const translated = ACTIVITY_KEYS[kind].map((key) => translate(key));
  const choices = translated.filter((message) => message !== previous);
  const pool = choices.length ? choices : translated;
  const index = Math.min(pool.length - 1, Math.max(0, Math.floor(random() * pool.length)));
  return pool[index];
}
