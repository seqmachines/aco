import { useState } from "react"
import { Settings as SettingsIcon, Moon, Sun, Key, Cpu, X, Eye, EyeOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { Settings as SettingsType } from "@/hooks/useSettings"

interface SettingsProps {
  isOpen: boolean
  onClose: () => void
  settings: SettingsType
  onUpdateSettings: (updates: Partial<SettingsType>) => void
  theme: "light" | "dark"
  onToggleTheme: () => void
  availableModels: { id: string; name: string; description: string }[]
}

export function Settings({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  theme,
  onToggleTheme,
  availableModels,
}: SettingsProps) {
  const [showApiKey, setShowApiKey] = useState(false)
  const [apiKeyInput, setApiKeyInput] = useState(settings.apiKey)

  if (!isOpen) return null

  const handleSaveApiKey = () => {
    onUpdateSettings({ apiKey: apiKeyInput })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <Card className="w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <SettingsIcon className="h-5 w-5" />
              Settings
            </CardTitle>
            <CardDescription>Configure aco preferences</CardDescription>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Theme Toggle */}
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label className="flex items-center gap-2">
                {theme === "dark" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
                Theme
              </Label>
              <p className="text-sm text-muted-foreground">
                Switch between light and dark mode
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={onToggleTheme}>
              {theme === "dark" ? "Light" : "Dark"}
            </Button>
          </div>

          {/* Model Selection */}
          <div className="space-y-3">
            <Label className="flex items-center gap-2">
              <Cpu className="h-4 w-4" />
              Gemini Model
            </Label>
            <div className="grid gap-2">
              {availableModels.map((model) => (
                <button
                  key={model.id}
                  onClick={() => onUpdateSettings({ model: model.id })}
                  className={`flex items-center justify-between p-3 rounded-lg border text-left transition-colors ${
                    settings.model === model.id
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-muted/50"
                  }`}
                >
                  <div>
                    <p className="font-medium text-sm">{model.name}</p>
                    <p className="text-xs text-muted-foreground">{model.description}</p>
                  </div>
                  {settings.model === model.id && (
                    <div className="h-2 w-2 rounded-full bg-primary" />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* API Key */}
          <div className="space-y-3">
            <Label className="flex items-center gap-2">
              <Key className="h-4 w-4" />
              Google API Key
            </Label>
            <p className="text-sm text-muted-foreground">
              Override the API key (leave empty to use server default)
            </p>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  type={showApiKey ? "text" : "password"}
                  placeholder="Enter API key..."
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                  onClick={() => setShowApiKey(!showApiKey)}
                >
                  {showApiKey ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                </Button>
              </div>
              <Button
                variant="outline"
                onClick={handleSaveApiKey}
                disabled={apiKeyInput === settings.apiKey}
              >
                Save
              </Button>
            </div>
            {settings.apiKey && (
              <p className="text-xs text-success">Custom API key is set</p>
            )}
          </div>

          {/* Info */}
          <div className="pt-4 border-t">
            <p className="text-xs text-muted-foreground text-center">
              Settings are saved locally in your browser
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
