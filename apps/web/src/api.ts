/**
 * Minimal API client for PCB-CDSO v0.6 web front-end.
 *
 * Uses native fetch (no axios) per ADR-0001 minimal-dependency stance.
 * Token is stored in memory + sessionStorage; refresh-on-401 is handled
 * by the caller (M2 simple polling, no transparent refresh interceptor
 * yet to keep the surface small).
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? '/'

export interface UserPublic {
  id: string
  email: string
  role: 'ADMIN' | 'ENGINEER'
  is_active: boolean
}

export interface ActorContext {
  actor_id: string
  role: 'ADMIN' | 'ENGINEER'
  locale: 'zh-CN' | 'en-US'
  theme: 'light' | 'dark'
}

export interface AuthSession {
  access_token: string
  refresh_token: string
  expires_in: number
  user: UserPublic
  locale: 'zh-CN' | 'en-US'
  theme: 'light' | 'dark'
}

export interface ProjectSummary {
  id: string
  name: string
  owner_id: string
  template_version_id: string
  country_code: string
  admin_area: string
  city: string
  timezone: string
  status: string
  created_at: string
}

export interface CreateProjectResponse {
  project: ProjectSummary
  inputRevision: number
  snapshotIds: string[]
  weatherTaskId: string
}

export interface TaskEnvelope {
  task_id: string
  status: 'DISPATCH_PENDING' | 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED' | 'STALE'
  progress: number
  stage: string
  processed: number
  total: number
  error: Record<string, unknown> | null
  retryable: boolean
}

export interface ApiErrorEnvelope {
  code: string
  message_key: string
  field_path: string | null
  details: Record<string, unknown>
  request_id: string
}

export class ApiError extends Error {
  constructor(public envelope: ApiErrorEnvelope, public status: number) {
    super(envelope.message_key)
    this.name = 'ApiError'
  }
}

const TOKEN_KEY = 'pcb-cdso:access-token:v1'
const REFRESH_KEY = 'pcb-cdso:refresh-token:v1'

export function getAccessToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_KEY)
}

export function clearTokens(): void {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(REFRESH_KEY)
}

function setTokens(access: string, refresh: string): void {
  sessionStorage.setItem(TOKEN_KEY, access)
  sessionStorage.setItem(REFRESH_KEY, refresh)
}

async function request<T>(
  path: string,
  options: RequestInit & { accessToken?: string } = {},
): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const token = options.accessToken ?? getAccessToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const response = await fetch(new URL(path, API_BASE).toString(), {
    ...options,
    headers,
  })
  if (response.status === 204) {
    return undefined as T
  }
  const text = await response.text()
  const body = text ? JSON.parse(text) : null
  if (!response.ok) {
    throw new ApiError(body as ApiErrorEnvelope, response.status)
  }
  return body as T
}

// --- auth endpoints ---

export async function login(email: string, password: string): Promise<AuthSession> {
  const session = await request<AuthSession>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setTokens(session.access_token, session.refresh_token)
  return session
}

export async function logout(): Promise<void> {
  try {
    await request('/auth/logout', { method: 'POST' })
  } finally {
    clearTokens()
  }
}

export async function getCurrentActor(accessToken?: string): Promise<ActorContext> {
  return request<ActorContext>('/auth/me', { accessToken })
}

// --- project endpoints ---

export async function createProject(
  input: {
    name: string
    templateVersionId: string
    countryCode: string
    adminArea: string
    city: string
    timezone: string
  },
  idempotencyKey: string,
): Promise<CreateProjectResponse> {
  return request<CreateProjectResponse>('/projects', {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify(input),
  })
}

// --- task endpoints ---

export async function listTasks(opts: { projectId?: string; activeOnly?: boolean } = {}): Promise<{
  items: TaskEnvelope[]
}> {
  const params = new URLSearchParams()
  if (opts.projectId) params.set('projectId', opts.projectId)
  if (opts.activeOnly) params.set('activeOnly', 'true')
  const query = params.toString()
  return request<{ items: TaskEnvelope[] }>(`/tasks${query ? `?${query}` : ''}`)
}

export async function getTask(taskId: string): Promise<TaskEnvelope> {
  return request<TaskEnvelope>(`/tasks/${taskId}`)
}
