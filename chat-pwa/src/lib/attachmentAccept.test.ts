import { describe, expect, it } from 'vitest';

import { DOCUMENT_FILE_ACCEPT, IMAGE_FILE_ACCEPT } from './attachmentAccept';

describe('native attachment picker filters', () => {
  it('allows camera or gallery images only from the image action', () => {
    expect(IMAGE_FILE_ACCEPT).toBe('image/*');
  });

  it('keeps image types out of the document action', () => {
    expect(DOCUMENT_FILE_ACCEPT).toContain('.pdf');
    expect(DOCUMENT_FILE_ACCEPT).toContain('.docx');
    expect(DOCUMENT_FILE_ACCEPT).not.toMatch(/image|\.png|\.jpe?g|\.heic|\.webp/i);
  });
});
