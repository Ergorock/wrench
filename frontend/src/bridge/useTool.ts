import { toolCall } from './client'

export function useTool(toolId: string) {
  return {
    call<T>(action: string, payload?: object): Promise<T> {
      return toolCall<T>(toolId, action, payload)
    },
  }
}
