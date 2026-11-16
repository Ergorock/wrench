import { describe, expect, it } from 'vitest'
import { countEdas, filterRows, sortRows, toggleAll } from '../src/tools/m3/logic'

describe('filterRows', () => {
  const rows = [{ n: 'Alpha', d: 'first' }, { n: 'Beta', d: 'ALPHA twin' }, { n: 'Gamma', d: '' }]

  it('keeps every row for a blank query', () => {
    expect(filterRows(rows, '  ', (r) => [r.n, r.d])).toEqual(rows)
  })

  it('matches any field, ignoring case', () => {
    expect(filterRows(rows, 'alpha', (r) => [r.n, r.d]).map((r) => r.n)).toEqual(['Alpha', 'Beta'])
  })
})

describe('sortRows', () => {
  it('sorts numbers numerically and text naturally, without touching the input', () => {
    const rows = [{ n: 'a10' }, { n: 'a2' }]
    expect(sortRows(rows, (r) => r.n, false).map((r) => r.n)).toEqual(['a2', 'a10'])
    expect(sortRows(rows, (r) => r.n, true).map((r) => r.n)).toEqual(['a10', 'a2'])
    expect(rows[0].n).toBe('a10')
    expect(sortRows([{ n: 10 }, { n: 9 }], (r) => r.n, false).map((r) => r.n)).toEqual([9, 10])
  })
})

describe('countEdas', () => {
  it('counts distinct first columns and skips blank lines', () => {
    expect(countEdas('A;x\r\n\r\nB\tz\nA\n')).toBe(2)
    expect(countEdas('')).toBe(0)
  })
})

describe('toggleAll', () => {
  it('selects every visible id, keeps hidden ones, and clears when all are selected', () => {
    const all = toggleAll(new Set(['hidden']), ['a', 'b'])
    expect([...all].sort()).toEqual(['a', 'b', 'hidden'])
    expect([...toggleAll(all, ['a', 'b'])]).toEqual(['hidden'])
    expect(toggleAll(new Set(['a']), ['a', 'b']).has('b')).toBe(true)
    expect(toggleAll(new Set(), []).size).toBe(0)
  })
})
