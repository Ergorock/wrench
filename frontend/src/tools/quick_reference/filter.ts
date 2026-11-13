/** Lowercase, accent-free text with single spaces: « Écran  DE » → « ecran de ». */
export function normalize(s: string): string {
  return s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/\s+/g, ' ').trim()
}

/**
 * An empty query matches everything. Otherwise every word of the query must appear, as a
 * substring, in the description or in the command.
 */
export function matches(description: string, command: string, query: string): boolean {
  const q = normalize(query)
  if (q === '') return true
  const haystack = normalize(`${description} ${command}`)
  return q.split(' ').every((word) => haystack.includes(word))
}
