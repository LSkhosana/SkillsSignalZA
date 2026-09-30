const PUBLIC_URL_MESSAGE = 'Enter a full public URL starting with https://.';

export function validateEvidenceUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return PUBLIC_URL_MESSAGE;
  }

  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return PUBLIC_URL_MESSAGE;
  }

  if (!url.hostname || !url.hostname.includes('.')) {
    return PUBLIC_URL_MESSAGE;
  }

  return null;
}
