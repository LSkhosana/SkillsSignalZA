import {
  DOCX_MEDIA_TYPE,
  MAX_CV_BYTES,
  PDF_MEDIA_TYPE,
  SUPPORTED_CV_MEDIA_TYPES,
} from '@/lib/constants';
import type { PickedCvDocument } from '@/services/api';

const EXTENSION_MEDIA_TYPES: Record<string, string> = {
  pdf: PDF_MEDIA_TYPE,
  docx: DOCX_MEDIA_TYPE,
};

export function mediaTypeFromName(name: string, mimeType?: string | null): string {
  if (mimeType && SUPPORTED_CV_MEDIA_TYPES.includes(mimeType as (typeof SUPPORTED_CV_MEDIA_TYPES)[number])) {
    return mimeType;
  }
  const extension = name.split('.').pop()?.toLowerCase() ?? '';
  return EXTENSION_MEDIA_TYPES[extension] ?? mimeType ?? '';
}

export function validatePickedCv(document: PickedCvDocument): string | null {
  const mediaType = mediaTypeFromName(document.name, document.mimeType);
  if (!SUPPORTED_CV_MEDIA_TYPES.includes(mediaType as (typeof SUPPORTED_CV_MEDIA_TYPES)[number])) {
    return 'Please choose a PDF or DOCX file.';
  }
  if (document.size != null && document.size > MAX_CV_BYTES) {
    return 'The CV must be 10 MB or smaller.';
  }
  return null;
}
