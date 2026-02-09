import { useState, useEffect, useCallback } from "react"
import type { IntakeFormData } from "@/types"

const STORAGE_KEY_BASE = "aco_intake_draft"

export function useAutoSave(scopeKey?: string | null) {
  const [savedData, setSavedData] = useState<IntakeFormData | null>(null)
  const storageKey = scopeKey
    ? `${STORAGE_KEY_BASE}:${scopeKey}`
    : null

  // Load saved data whenever the storage scope changes
  useEffect(() => {
    if (!storageKey) {
      setSavedData(null)
      return
    }

    try {
      const stored = localStorage.getItem(storageKey)
      if (stored) {
        const parsed = JSON.parse(stored) as IntakeFormData
        setSavedData(parsed)
      } else {
        setSavedData(null)
      }
    } catch {
      // Invalid data, clear it
      localStorage.removeItem(storageKey)
      setSavedData(null)
    }
  }, [storageKey])

  // Save data with debouncing handled by caller
  const saveData = useCallback((data: IntakeFormData) => {
    if (!storageKey) return

    try {
      localStorage.setItem(storageKey, JSON.stringify(data))
      setSavedData(data)
    } catch {
      // Storage full or unavailable
      console.warn("Failed to save draft to localStorage")
    }
  }, [storageKey])

  // Clear saved data
  const clearData = useCallback(() => {
    if (!storageKey) return

    try {
      localStorage.removeItem(storageKey)
      setSavedData(null)
    } catch {
      // Ignore
    }
  }, [storageKey])

  return { savedData, saveData, clearData }
}
