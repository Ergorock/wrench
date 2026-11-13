// Mirrors of the Pydantic models in backend/src/wrench/tools/converters/service.py.
export interface UnitCategory {
  id: string
  units: string[]
}

export interface Units {
  categories: UnitCategory[]
}

export interface Rate {
  code: string
  rate: number
  date: string
}

export interface Rates {
  base: string
  rates: Rate[]
}
