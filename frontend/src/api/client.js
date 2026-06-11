import axios from 'axios'

const API_BASE_URL = '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Games API
export const gamesAPI = {
  list: () => api.get('/games'),
  create: (data) => api.post('/games', data),
  get: (id) => api.get(`/games/${id}`),
  update: (id, data) => api.put(`/games/${id}`, data),
  uploadCover: (id, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/games/${id}/cover`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  delete: (id) => api.delete(`/games/${id}`),
}

// Documents API
export const documentsAPI = {
  list: (gameId) => api.get(`/documents/${gameId}`),
  upload: (gameId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/documents/${gameId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  rebuildReport: (id) => api.post(`/documents/${id}/processing-report`),
  reprocess: (id) => api.post(`/documents/${id}/reprocess`),
  update: (id, data) => api.put(`/documents/${id}`, data),
  listChunks: (id) => api.get(`/documents/${id}/chunks`),
  updateChunk: (id, data) => api.put(`/documents/chunks/${id}`, data),
  splitChunk: (id, splitAt) => api.post(`/documents/chunks/${id}/split`, { split_at: splitAt }),
  mergeChunkNext: (id) => api.post(`/documents/chunks/${id}/merge-next`),
  listLayoutRegions: (id, params = {}) => api.get(`/documents/${id}/layout-regions`, { params }),
  createLayoutRegion: (id, data) => api.post(`/documents/${id}/layout-regions`, data),
  updateLayoutRegion: (id, data) => api.put(`/documents/layout-regions/${id}`, data),
  deleteLayoutRegion: (id) => api.delete(`/documents/layout-regions/${id}`),
  delete: (id) => api.delete(`/documents/${id}`),
}

// Chat API
export const chatAPI = {
  ask: (gameId, message, options = {}) => api.post(`/chat/${gameId}/ask`, {
    message,
    ...(options.displayMessage ? { display_message: options.displayMessage } : {}),
    ...(options.retrievalMessage ? { retrieval_message: options.retrievalMessage } : {}),
    ...(options.answerMode ? { answer_mode: options.answerMode } : {}),
  }),
  askStream: async (gameId, message, options = {}) => {
    const response = await fetch(`${API_BASE_URL}/chat/${gameId}/ask-stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        ...(options.displayMessage ? { display_message: options.displayMessage } : {}),
        ...(options.retrievalMessage ? { retrieval_message: options.retrievalMessage } : {}),
        ...(options.answerMode ? { answer_mode: options.answerMode } : {}),
      }),
    })

    if (!response.ok || !response.body) {
      throw new Error(`Stream request failed: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const parseEvent = (rawEvent) => {
      const lines = rawEvent.split('\n')
      let event = 'message'
      const dataLines = []
      for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
      }
      if (!dataLines.length) return null
      return { event, data: JSON.parse(dataLines.join('\n')) }
    }

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''
      for (const rawEvent of events) {
        const parsed = parseEvent(rawEvent)
        if (parsed) options.onEvent?.(parsed)
      }
    }

    buffer += decoder.decode()
    if (buffer.trim()) {
      const parsed = parseEvent(buffer)
      if (parsed) options.onEvent?.(parsed)
    }
  },
  history: (gameId, limit = 50, offset = 0) =>
    api.get(`/chat/${gameId}/history`, { params: { limit, offset } }),
  expand: (id) => api.post(`/chat/messages/${id}/expand`),
  deleteMessage: (id) => api.delete(`/chat/${id}`),
}

// Evaluation API
export const evalsAPI = {
  generateCandidates: (gameId, params = {}) =>
    api.post(`/evals/${gameId}/candidate-questions`, null, { params }),
  promoteCandidates: (gameId) => api.post(`/evals/${gameId}/promote-candidates`),
  listCases: (gameId, params = {}) => api.get(`/evals/${gameId}/cases`, { params }),
  updateCase: (caseId, data) => api.put(`/evals/cases/${caseId}`, data),
  run: (gameId, params = {}) => api.post(`/evals/${gameId}/run`, null, { params }),
  runChat: (gameId, params = {}) => api.post(`/evals/${gameId}/run-chat`, null, { params }),
  latestRun: (gameId, params = {}) => api.get(`/evals/${gameId}/latest-run`, { params }),
  failureAnalysis: (gameId, params = {}) => api.get(`/evals/${gameId}/failure-analysis`, { params }),
}

// Glossary API
export const glossaryAPI = {
  list: (gameId, params = {}) => api.get(`/glossary/${gameId}`, { params }),
  regenerate: (gameId) => api.post(`/glossary/${gameId}/regenerate`),
  updateTerm: (id, data) => api.put(`/glossary/terms/${id}`, data),
}

// Curated visual assets API
export const assetsAPI = {
  list: (gameId, params = {}) => api.get(`/assets/${gameId}`, { params }),
  pagePreview: (gameId, documentId, page) =>
    api.get(`/assets/${gameId}/page`, { params: { document_id: documentId, page } }),
  create: (gameId, data) => api.post(`/assets/${gameId}`, data),
  regenerate: (gameId) => api.post(`/assets/${gameId}/regenerate`),
  regenerateOne: (id) => api.post(`/assets/items/${id}/regenerate`),
  update: (id, data) => api.put(`/assets/${id}`, data),
  delete: (id) => api.delete(`/assets/${id}`),
}

// Settings API
export const settingsAPI = {
  getModelConfig: () => api.get('/settings/model-config'),
  updateModelConfig: (data) => api.put('/settings/model-config', data),
}

export default api
