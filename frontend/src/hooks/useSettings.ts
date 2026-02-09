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
  { id: "gemini-3-pro-preview", name: "Gemini 3 Pro", description: "Broad reasoning across modalities" },
  { id: "gemini-3-flash-preview", name: "Gemini 3 Flash", description: "Pro-level intelligence at speed" },
  { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro", description: "Advanced reasoning (Stable)" },
  { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", description: "Fast and balanced (Stable)" },
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
