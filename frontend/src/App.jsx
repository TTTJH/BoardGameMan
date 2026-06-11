import React from 'react'
import { Toaster } from 'react-hot-toast'
import { BookOpen, Settings, SlidersHorizontal } from 'lucide-react'
import { useGameStore } from './store'
import { gamesAPI } from './api/client'
import GameList from './components/GameList'
import GameDetail from './components/GameDetail'
import ModelSettings from './components/ModelSettings'
import { LanguageSwitcher, useI18n } from './i18n'
import './index.css'

function App() {
  const { games, setGames, currentGame, setCurrentGame, setLoading } = useGameStore()
  const { t } = useI18n()
  const [initialized, setInitialized] = React.useState(false)
  const [settingsOpen, setSettingsOpen] = React.useState(false)
  const [mode, setMode] = React.useState('lounge')

  React.useEffect(() => {
    loadGames()
  }, [])

  const loadGames = async () => {
    setLoading(true)
    try {
      const response = await gamesAPI.list()
      setGames(response.data)
    } catch (error) {
      console.error('Failed to load games')
    } finally {
      setLoading(false)
      setInitialized(true)
    }
  }

  const switchMode = (nextMode) => {
    setMode(nextMode)
    setCurrentGame(null)
  }

  return (
    <div className="min-h-screen steam-app">
      <Toaster position="top-right" />

      <header className="steam-header">
        <div className="container flex items-center justify-between gap-4 py-3">
          <div>
            <h1 className="text-xl font-bold tracking-wide text-slate-100">
              Board Game Rulebook AI
            </h1>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
              {mode === 'admin' ? t('app.subtitle.admin') : t('app.subtitle.lounge')}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <LanguageSwitcher />
            <button
              onClick={() => switchMode('lounge')}
              className={mode === 'lounge' ? 'steam-action' : 'steam-ghost'}
            >
              <BookOpen size={18} />
              {t('nav.gameLounge')}
            </button>
            <button
              onClick={() => switchMode('admin')}
              className={mode === 'admin' ? 'steam-action' : 'steam-ghost'}
            >
              <SlidersHorizontal size={18} />
              {t('nav.adminKitchen')}
            </button>
            {mode === 'admin' && (
              <button
                onClick={() => setSettingsOpen(true)}
                className="steam-ghost flex items-center gap-2"
                aria-label={t('nav.openModelSettings')}
              >
                <Settings size={18} />
                {t('nav.modelSettings')}
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="container py-5">
        {initialized ? (
          currentGame ? (
            <GameDetail
              game={currentGame}
              onBack={() => setCurrentGame(null)}
              mode={mode}
            />
          ) : (
            <GameList onSelectGame={setCurrentGame} mode={mode} />
          )
        ) : (
          <div className="flex h-64 items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600"></div>
              <p className="text-slate-400">{t('app.loading')}</p>
            </div>
          </div>
        )}
      </main>

      <footer className="steam-footer">
        <div className="container py-3 text-center text-xs text-slate-500">
          <p>Board Game Rulebook AI Assistant 2024</p>
        </div>
      </footer>

      <ModelSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

export default App
