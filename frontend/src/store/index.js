import { create } from 'zustand'

export const useGameStore = create((set) => ({
  games: [],
  currentGame: null,
  loading: false,
  error: null,

  setGames: (games) => set({ games }),
  setCurrentGame: (game) => set({ currentGame: game }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  addGame: (game) => set((state) => ({
    games: [game, ...state.games],
  })),

  removeGame: (id) => set((state) => ({
    games: state.games.filter((g) => g.id !== id),
  })),

  updateGame: (game) => set((state) => ({
    games: state.games.map((g) => (g.id === game.id ? game : g)),
    currentGame: state.currentGame?.id === game.id ? game : state.currentGame,
  })),
}))

export const useChatStore = create((set) => ({
  messages: [],
  loading: false,
  error: null,

  setMessages: (messages) => set((state) => ({
    messages: typeof messages === 'function' ? messages(state.messages) : messages,
  })),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message],
  })),

  clearMessages: () => set({ messages: [] }),
}))

export const useDocumentStore = create((set) => ({
  documents: [],
  uploading: false,
  error: null,

  setDocuments: (documents) => set({ documents }),
  setUploading: (uploading) => set({ uploading }),
  setError: (error) => set({ error }),

  addDocument: (doc) => set((state) => ({
    documents: [doc, ...state.documents],
  })),

  removeDocument: (id) => set((state) => ({
    documents: state.documents.filter((d) => d.id !== id),
  })),
}))
