import { useState, useEffect, useRef, useCallback } from "react"
import {
  MessageSquare,
  Send,
  Loader2,
  PanelRightClose,
  PanelRight,
  Trash2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { useChat } from "@/hooks/useApi"
import type { AppStep, ChatMessage } from "@/types"

interface ChatPanelProps {
  manifestId: string | undefined
  currentStep: AppStep
  collapsed: boolean
  onToggle: () => void
  onArtifactUpdate?: (step: AppStep, data: Record<string, unknown>) => void
}

const stepLabels: Record<string, string> = {
  intake: "Experiment Setup",
  scanning: "File Scanning",
  manifest: "Run Data Review",
  understanding: "Analysis & Plan",
  scripts: "Script Planning",
  notebook: "Notebook",
  report: "QC Report",
  approved: "Complete",
}

export function ChatPanel({
  manifestId,
  currentStep,
  collapsed,
  onToggle,
  onArtifactUpdate,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const chatEndRef = useRef<HTMLDivElement>(null)
  const prevStepRef = useRef<AppStep>(currentStep)
  const prevManifestRef = useRef<string | undefined>(manifestId)

  const { sendMessage, getHistory, clearHistory, isLoading } = useChat()

  // Load chat history when step or manifest changes
  useEffect(() => {
    if (!manifestId) {
      setMessages([])
      return
    }

    // Only reload if step or manifest actually changed
    if (
      currentStep === prevStepRef.current &&
      manifestId === prevManifestRef.current
    ) {
      return
    }

    prevStepRef.current = currentStep
    prevManifestRef.current = manifestId

    const loadHistory = async () => {
      const history = await getHistory(manifestId, currentStep)
      setMessages(history)
    }
    loadHistory()
  }, [currentStep, manifestId, getHistory])

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSend = useCallback(async () => {
    if (!input.trim() || !manifestId || isLoading) return

    const userMessage: ChatMessage = {
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput("")

    const result = await sendMessage(manifestId, currentStep, userMessage.content)

    if (result) {
      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: result.response,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMessage])

      if (result.artifact_updated && result.updated_data && onArtifactUpdate) {
        onArtifactUpdate(currentStep, result.updated_data)
      }
    } else {
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: "Sorry, I encountered an error processing your message. Please try again.",
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
    }
  }, [input, manifestId, currentStep, isLoading, sendMessage, onArtifactUpdate])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleClear = useCallback(async () => {
    if (!manifestId) return
    await clearHistory(manifestId, currentStep)
    setMessages([])
  }, [manifestId, currentStep, clearHistory])

  // Collapsed state: just show the toggle button
  if (collapsed) {
    return (
      <div className="border-l border-border bg-card/50 flex flex-col items-center py-4 w-10">
        <button
          onClick={onToggle}
          className="p-1.5 rounded hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
          title="Open chat"
        >
          <PanelRight className="h-4 w-4" />
        </button>
        <div className="mt-3 writing-mode-vertical text-[10px] text-muted-foreground font-medium tracking-wider"
          style={{ writingMode: "vertical-rl", textOrientation: "mixed" }}
        >
          Chat
        </div>
        {messages.length > 0 && (
          <Badge variant="secondary" className="mt-2 text-[9px] px-1 py-0 min-w-0">
            {messages.length}
          </Badge>
        )}
      </div>
    )
  }

  // No manifest = nothing to chat about
  if (!manifestId) {
    return (
      <div className="border-l border-border bg-card/50 w-80 flex flex-col">
        <div className="flex items-center justify-between p-3 border-b border-border">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Chat</span>
          </div>
          <button
            onClick={onToggle}
            className="p-1 rounded hover:bg-muted/50 text-muted-foreground hover:text-foreground"
            title="Close chat"
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-sm text-muted-foreground text-center">
            Submit an experiment to start chatting
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="border-l border-border bg-card/50 w-80 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border">
        <div className="flex items-center gap-2 min-w-0">
          <MessageSquare className="h-4 w-4 text-primary flex-shrink-0" />
          <span className="text-sm font-medium truncate">
            {stepLabels[currentStep] || currentStep}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {messages.length > 0 && (
            <button
              onClick={handleClear}
              className="p-1 rounded hover:bg-muted/50 text-muted-foreground hover:text-foreground"
              title="Clear history"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            onClick={onToggle}
            className="p-1 rounded hover:bg-muted/50 text-muted-foreground hover:text-foreground"
            title="Close chat"
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <MessageSquare className="h-8 w-8 text-muted-foreground/30 mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">
              Ask questions or provide feedback about the current step
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={cn(
              "text-sm p-2 rounded",
              msg.role === "user"
                ? "bg-primary/10 text-foreground ml-6"
                : "bg-muted text-foreground mr-6"
            )}
          >
            <span className="text-[10px] font-medium text-muted-foreground block mb-0.5">
              {msg.role === "user" ? "You" : "Acolyte"}
            </span>
            <div className="whitespace-pre-wrap text-xs">{msg.content}</div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground mr-6 p-2">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span className="text-xs">Thinking...</span>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-border">
        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question..."
            className="min-h-[60px] max-h-[120px] resize-none text-xs"
            disabled={isLoading}
          />
          <Button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            size="sm"
            className="self-end h-8 w-8 p-0"
          >
            {isLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
