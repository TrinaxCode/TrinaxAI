import { describe, expect, it } from 'vitest';

import { appendAttachmentSelection, DOCUMENT_FILE_ACCEPT, filesFromDataTransfer, imageFilesFrom, IMAGE_FILE_ACCEPT, MAX_ATTACHMENTS_PER_TYPE } from './attachmentAccept';

describe('native attachment picker filters', () => {
  it('allows camera or gallery images only from the image action', () => {
    expect(IMAGE_FILE_ACCEPT).toBe('image/*');
  });

  it('keeps image types out of the document action', () => {
    expect(DOCUMENT_FILE_ACCEPT).toContain('.pdf');
    expect(DOCUMENT_FILE_ACCEPT).toContain('.docx');
    expect(DOCUMENT_FILE_ACCEPT).not.toMatch(/image|\.png|\.jpe?g|\.heic|\.webp/i);
  });

  it('caps each attachment type at three files', () => {
    expect(MAX_ATTACHMENTS_PER_TYPE).toBe(3);
  });

  it('keeps earlier attachments when a picker is used again', () => {
    expect(appendAttachmentSelection(['one.pdf', 'two.pdf'], ['three.pdf', 'four.pdf'])).toEqual([
      'one.pdf', 'two.pdf', 'three.pdf',
    ]);
  });

  it('reads files from clipboard and drag-and-drop data', () => {
    const image = new File(['image'], 'photo.png', { type: 'image/png' });
    const document = new File(['text'], 'notes.txt', { type: 'text/plain' });
    const data = { files: [image, document], items: [] } as unknown as DataTransfer;

    expect(filesFromDataTransfer(data)).toEqual([image, document]);
    expect(imageFilesFrom([image, document])).toEqual([image]);
  });

  it('falls back to file clipboard items when the files list is empty', () => {
    const image = new File(['image'], 'photo.png', { type: 'image/png' });
    const data = {
      files: [],
      items: [{ kind: 'file', getAsFile: () => image }],
    } as unknown as DataTransfer;

    expect(filesFromDataTransfer(data)).toEqual([image]);
  });
});
