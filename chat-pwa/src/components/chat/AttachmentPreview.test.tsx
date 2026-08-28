import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AttachmentPreview from './AttachmentPreview';

vi.mock('../../i18n/I18nContext', () => ({
  useI18n: () => ({ t: (key: string) => ({
    close: 'Close',
    openAttachment: 'Open',
    download: 'Download',
    mobileAttachmentHint: 'Use Download on your device.',
    chatAttachmentLocalOnly: 'Only on this device.',
    attachmentActionFailed: 'Could not open.',
  }[key] || key) }),
}));

const preview = {
  attachment: {
    name: 'manual.pdf',
    size: 12,
    mimeType: 'application/pdf',
    storageKey: `server:${'e'.repeat(32)}`,
    kind: 'document' as const,
  },
  url: 'blob:preview',
};

describe('AttachmentPreview', () => {
  it('shows mobile PDF fallback with explicit open and download actions', async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn().mockResolvedValue(true);
    const onDownload = vi.fn().mockResolvedValue(true);
    const { container } = render(
      <AttachmentPreview
        preview={{ ...preview, attachment: { ...preview.attachment, localOnly: true } }}
        textPreview={null}
        isDark={false}
        isMobile
        onOpen={onOpen}
        onDownload={onDownload}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText('Use Download on your device.')).toBeInTheDocument();
    expect(screen.getByText('Only on this device.')).toBeInTheDocument();
    expect(container.querySelector('object')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Open' }));
    await user.click(screen.getByRole('button', { name: 'Download' }));
    expect(onOpen).toHaveBeenCalledOnce();
    expect(onDownload).toHaveBeenCalledOnce();
  });

  it('keeps the native PDF object on desktop', () => {
    const { container } = render(
      <AttachmentPreview
        preview={preview}
        textPreview={null}
        isDark={false}
        isMobile={false}
        onOpen={vi.fn().mockResolvedValue(true)}
        onDownload={vi.fn().mockResolvedValue(true)}
        onClose={vi.fn()}
      />,
    );

    expect(document.body.querySelector('object[type="application/pdf"]')).toBeTruthy();
  });

  it('does not render SVG attachments as active images', () => {
    const { container } = render(
      <AttachmentPreview
        preview={{ ...preview, attachment: { ...preview.attachment, name: 'icon.svg', mimeType: 'image/svg+xml' } }}
        textPreview={null}
        isDark={false}
        isMobile={false}
        onOpen={vi.fn().mockResolvedValue(false)}
        onDownload={vi.fn().mockResolvedValue(true)}
        onClose={vi.fn()}
      />,
    );

    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByText('downloadFileToOpen')).toBeInTheDocument();
  });
});
