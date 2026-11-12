/** Lowercase, accent-free text with single spaces: « Écran  DE » → « ecran de ». */
export function normalize(s: string): string {
  return s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/\s+/g, ' ').trim()
}

export interface SearchEntry {
  id: string
  description: string
  keyLabels: string[]
  keyIds: string[]
}

/**
 * An empty query matches everything. Otherwise every word of the query must appear as a
 * substring of the description, the displayed key labels or the raw key ids.
 */
export function matches(entry: SearchEntry, query: string): boolean {
  const q = normalize(query)
  if (q === '') return true
  const haystack = normalize(
    `${entry.description} ${entry.keyLabels.join(' ')} ${entry.keyIds.join(' ')}`,
  )
  return q.split(' ').every((word) => haystack.includes(word))
}
