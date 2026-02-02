import { useState, useEffect, useCallback } from "react"
import type { IntakeFormData } from "@/types"

const STORAGE_KEY = "aco_intake_draft"

export function useAutoSave() {
  const [savedData, setSavedData] = useState<IntakeFormData | null>(null)

  // Load saved data on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored) as IntakeFormData
        setSavedData(parsed)
      }
    } catch {
      // Invalid data, clear it
      localStorage.removeItem(STORAGE_KEY)
    }
  }, [])

  // Save data with debouncing handled by caller
  const saveData = useCallback((data: IntakeFormData) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
      setSavedData(data)
    } catch {
      // Storage full or unavailable
      console.warn("Failed to save draft to localStorage")
    }
  }, [])

  // Clear saved data
  const clearData = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY)
      setSavedData(null)
    } catch {
      // Ignore
    }
  }, [])

  return { savedData, saveData, clearData }
}
