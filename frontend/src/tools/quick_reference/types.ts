// Mirrors of the Pydantic models in backend/src/wrench/tools/quick_reference/service.py.
export interface Entry {
  id: string
  command: string
}

export interface Sheet {
  id: string
  entries: Entry[]
}

export interface Reference {
  sheets: Sheet[]
}
