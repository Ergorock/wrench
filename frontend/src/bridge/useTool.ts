import { BridgeError, toolCall } from './client'
import { toastError } from '../shell/toasts'

export function useTool(toolId: string) {
  return {
    async call<T>(action: string, payload?: object): Promise<T> {
      try {
        return await toolCall<T>(toolId, action, payload)
      } catch (err) {
        if (err instanceof BridgeError) toastError(err, toolId)
        throw err
      }
    },
  }
}
