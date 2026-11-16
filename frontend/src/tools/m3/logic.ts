/** Rows whose given fields contain `query` (case-insensitive); all rows when `query` is blank. */
export function filterRows<T>(rows: T[], query: string, fields: (row: T) => string[]): T[] {
  const needle = query.trim().toLowerCase()
  if (needle === '') return rows
  return rows.filter((row) => fields(row).some((f) => f.toLowerCase().includes(needle)))
}

export function sortRows<T>(rows: T[], key: (row: T) => string | number, desc: boolean): T[] {
  const sign = desc ? -1 : 1
  return [...rows].sort((a, b) => {
    const x = key(a)
    const y = key(b)
    if (typeof x === 'number' && typeof y === 'number') return sign * (x - y)
    return sign * String(x).localeCompare(String(y), undefined, { numeric: true, sensitivity: 'base' })
  })
}

/** EDA identifiers typed or pasted, one per line: the number of distinct, non-empty first columns. */
export function countEdas(text: string): number {
  const ids = text
    .split(/\r?\n/)
    .map((line) => line.split(/[;\t,]/)[0].trim())
    .filter((id) => id !== '')
  return new Set(ids).size
}
