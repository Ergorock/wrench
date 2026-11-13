// Mirrors of the Pydantic models in backend/src/wrench/tools/qr_barcode/service.py.
export type SymbolKind = 'qr' | 'barcode'

export interface Code {
  kind: SymbolKind
  data: string
  barcode_type: string
}

export interface Picture {
  svg: string
}

export interface Exported {
  path: string
}
