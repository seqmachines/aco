import { useState, useEffect, useCallback } from "react"

export interface Settings {
  apiKey: string
  model: string
}

const DEFAULT_SETTINGS: Settings = {
  apiKey: "",
  model: "gemini-3-pro-preview",
}

const AVAILABLE_MODELS = [
  { id: "gemini-3-pro-preview", name: "Gemini 3 Pro", description: "Latest and most capable" },
  { id: "gemini-2.5-pro-preview-06-05", name: "Gemini 2.5 Pro", description: "Very capable" },
  { id: "gemini-2.5-flash-preview-05-20", name: "Gemini 2.5 Flash", description: "Fast with great quality" },
  { id: "gemini-2.0-flash", name: "Gemini 2.0 Flash", description: "Fast and efficient" },
]

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(() => {
    const saved = localStorage.getItem("aco-settings")
    if (saved) {
      try {
        return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) }
      } catch {
        return DEFAULT_SETTINGS
      }
    }
    return DEFAULT_SETTINGS
  })

  useEffect(() => {
    localStorage.setItem("aco-settings", JSON.stringify(settings))
  }, [settings])

  const updateSettings = useCallback((updates: Partial<Settings>) => {
    setSettings((prev) => ({ ...prev, ...updates }))
  }, [])

  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS)
  }, [])

  return {
    settings,
    updateSettings,
    resetSettings,
    availableModels: AVAILABLE_MODELS,
  }
}
