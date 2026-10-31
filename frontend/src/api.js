// Thin typed-ish client. Keys are held in sessionStorage only (prototype; never ship real keys in a browser).
export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function call(path, { method = 'GET', body, headers } = {}) {
  const res = await fetch('/api' + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...headers },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const message = data?.error?.message || `${res.status} ${res.statusText}`
    if (res.status === 401) throw new ApiError(`Authentication failed: ${message}`, res.status)
    throw new ApiError(message, res.status)
  }
  return data
}

async function uploadVoice(formData, serviceKey) {
  const res = await fetch('/api/v1/voice/chat', {
    method: 'POST',
    headers: { 'X-Api-Key': serviceKey },
    body: formData,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const message = data?.error?.message || data?.detail || `${res.status} ${res.statusText}`
    if (res.status === 401) throw new ApiError(`Authentication failed: ${message}`, res.status)
    throw new ApiError(message, res.status)
  }
  return data
}

export const makeApi = ({ serviceKey, opId, opKey }) => {
  const service = serviceKey.trim()
  const operatorId = opId.trim()
  const operatorKey = opKey.trim()
  const op = { 'X-Operator-Id': operatorId, 'X-Operator-Key': operatorKey }
  return {
    hasServiceCredentials: () => Boolean(service),
    hasOperatorCredentials: () => Boolean(operatorId && operatorKey),
    health: () => call('/health'),
    voiceStatus: () => call('/v1/voice/status', { headers: { 'X-Api-Key': service } }),
    chat: (merchant_id, message, session_id) =>
      call('/v1/chat', { method: 'POST', headers: { 'X-Api-Key': service }, body: { merchant_id, message, session_id } }),
    voiceSpeak: (text, language) => call('/v1/voice/speak', { method: 'POST', headers: { 'X-Api-Key': service }, body: { text, language } }),
    voiceChat: (merchant_id, audio, session_id) => {
      const formData = new FormData()
      const extension = audio.type.toLowerCase().includes('mp4') ? 'm4a' : 'webm'
      formData.append('audio', audio, `recording.${extension}`)
      formData.append('merchant_id', merchant_id)
      if (session_id) formData.append('session_id', session_id)
      return uploadVoice(formData, service)
    },
    whoami: () => call('/v1/operator/whoami', { headers: op }),
    approvals: () => call('/v1/approvals', { headers: op }),
    decide: (id, verb) => call(`/v1/approvals/${id}/${verb}`, { method: 'POST', headers: op, body: {} }),
    escalations: () => call('/v1/escalations', { headers: op }),
    closeEscalation: id => call(`/v1/escalations/${id}/close`, { method: 'POST', headers: op, body: {} }),
    audit: () => call('/v1/audit?limit=60', { headers: op }),
    verifyAudit: () => call('/v1/audit/verify', { headers: op }),
  }
}

