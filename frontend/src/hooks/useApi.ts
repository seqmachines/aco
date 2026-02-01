import { useState, useCallback } from "react"
import type {
  IntakeResponse,
  ScanResponse,
  ManifestResponse,
  UnderstandingResponse,
  ApprovalResponse,
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

// Intake hook
export function useIntake() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submitIntake = useCallback(
    async (data: {
      experiment_description: string
      target_directory: string
      goals?: string
      known_issues?: string
      additional_notes?: string
    }): Promise<IntakeResponse | null> => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`${API_BASE}/intake`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        })

        return await handleResponse<IntakeResponse>(response)
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
