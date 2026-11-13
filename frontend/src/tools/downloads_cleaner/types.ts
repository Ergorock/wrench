// Mirrors of the Pydantic models in backend/src/wrench/tools/downloads_cleaner/service.py.
export interface Filters {
  folder: string
  extensions: string[]
  min_age_days: number
  min_size_mb: number
}

export interface Candidate {
  name: string
  size: number
  modified: string
}

export interface Scan {
  folder: string
  files: Candidate[]
  total_size: number
}

export interface Failure {
  name: string
  reason: string
}

export interface Applied {
  removed: string[]
  failed: Failure[]
}
