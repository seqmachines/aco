import { useState, useCallback, useEffect } from "react"
import type {
  IntakeResponse,
  ScanResponse,
  ManifestResponse,
  UnderstandingResponse,
  ApprovalResponse,
  ConfigResponse,
  IntakeFormData,
} from "@/types"

// In production, API is served from same origin. In dev, proxy handles /api -> :8000
const API_BASE = ""

interface ApiError {
  detail: string
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      detail: `HTTP error ${response.status}`,
    }))
    throw new Error(error.detail)
  }
  return response.json()
}

// Config hook
export function useConfig() {
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    async function fetchConfig() {
      try {
        const response = await fetch(`${API_BASE}/api/config`)
        if (response.ok) {
          const data = await response.json()
          setConfig(data)
        }
      } catch {
        // Config endpoint not available, use defaults
      } finally {
        setIsLoading(false)
      }
    }
    fetchConfig()
  }, [])

  return { config, isLoading }
}

// Intake hook
export function useIntake() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submitIntake = useCallback(
    async (data: IntakeFormData): Promise<IntakeResponse | null> => {
      setIsLoading(true)
      setError(null)

      try {
        // Check if we have files to upload
        if (data.uploaded_files && data.uploaded_files.length > 0) {
          // Use multipart form data for file uploads
          const formData = new FormData()
          formData.append("experiment_description", data.experiment_description)
          formData.append("target_directory", data.target_directory)
          if (data.goals) formData.append("goals", data.goals)
          if (data.known_issues) formData.append("known_issues", data.known_issues)
          if (data.additional_notes) formData.append("additional_notes", data.additional_notes)

          // Add files - convert from UploadedFile back to File-like blobs
          for (const file of data.uploaded_files) {
            if (file.dataUrl) {
              // Convert data URL to blob
              const response = await fetch(file.dataUrl)
              const blob = await response.blob()
              formData.append("documents", blob, file.name)
            } else if (file.content) {
              const blob = new Blob([file.content], { type: file.type || "text/plain" })
              formData.append("documents", blob, file.name)
            }
          }

          const response = await fetch(`${API_BASE}/intake/with-documents`, {
            method: "POST",
            body: formData,
          })

          return await handleResponse<IntakeResponse>(response)
        } else {
          // Simple JSON request without files
          const response = await fetch(`${API_BASE}/intake`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              experiment_description: data.experiment_description,
              target_directory: data.target_directory,
              goals: data.goals,
              known_issues: data.known_issues,
              additional_notes: data.additional_notes,
            }),
          })

          return await handleResponse<IntakeResponse>(response)
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to submit intake"
        setError(message)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  return { submitIntake, isLoading, error }
}

// Scan hook
export function useScan() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const scanDirectory = useCallback(
    async (
      targetDirectory: string,
      maxDepth = 10
    ): Promise<ScanResponse | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`${API_BASE}/scan`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_directory: targetDirectory,
            max_depth: maxDepth,
          }),
        })

        return await handleResponse<ScanResponse>(response)
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to scan directory"
        setError(message)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  return { scanDirectory, isLoading, error }
}

// Manifest hook
export function useManifest() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const getManifest = useCallback(
    async (manifestId: string): Promise<ManifestResponse | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`${API_BASE}/manifest/${manifestId}`)
        return await handleResponse<ManifestResponse>(response)
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to get manifest"
        setError(message)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  const updateManifest = useCallback(
    async (
      manifestId: string,
      data: {
        experiment_description?: string
        goals?: string
        known_issues?: string
        additional_notes?: string
        rescan?: boolean
      }
    ): Promise<ManifestResponse | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`${API_BASE}/manifest/${manifestId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        })

        return await handleResponse<ManifestResponse>(response)
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to update manifest"
        setError(message)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  return { getManifest, updateManifest, isLoading, error }
}

// Understanding hook
export function useUnderstanding() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generateUnderstanding = useCallback(
    async (
      manifestId: string,
      regenerate = false
    ): Promise<UnderstandingResponse | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`${API_BASE}/understanding`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            manifest_id: manifestId,
            regenerate,
          }),
        })

        return await handleResponse<UnderstandingResponse>(response)
      } catch (e) {
        const message =
          e instanceof Error ? e.message : "Failed to generate understanding"
        setError(message)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  const getUnderstanding = useCallback(
    async (manifestId: string): Promise<UnderstandingResponse | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`${API_BASE}/understanding/${manifestId}`)
        return await handleResponse<UnderstandingResponse>(response)
      } catch (e) {
        const message =
          e instanceof Error ? e.message : "Failed to get understanding"
        setError(message)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  const approveUnderstanding = useCallback(
    async (
      manifestId: string,
      edits?: Record<string, string>,
      feedback?: string
    ): Promise<ApprovalResponse | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(
          `${API_BASE}/understanding/${manifestId}/approve`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ edits, feedback }),
          }
        )

        return await handleResponse<ApprovalResponse>(response)
      } catch (e) {
        const message =
          e instanceof Error ? e.message : "Failed to approve understanding"
        setError(message)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  return {
    generateUnderstanding,
    getUnderstanding,
    approveUnderstanding,
    isLoading,
    error,
  }
}
