import React from 'react'
import { CalendarDays, FileText, Pencil, Plus, Save, Search, Trash2, Upload, X } from 'lucide-react'
import { useGameStore } from '../store'
import { gamesAPI } from '../api/client'
import toast from 'react-hot-toast'
import { useI18n } from '../i18n'

const coverPalettes = [
  ['#14305c', '#00a8ff', '#10213c'],
  ['#49111c', '#f15025', '#161a1d'],
  ['#1f3b2c', '#8ac926', '#081c15'],
  ['#2d1b69', '#ff4d6d', '#10002b'],
  ['#49380f', '#ffd166', '#1d1b12'],
  ['#132a13', '#4cc9f0', '#0b132b'],
  ['#451952', '#f39c12', '#1d1028'],
  ['#1d3557', '#e63946', '#0b1320'],
]

function hashString(value) {
  return [...value].reduce((hash, char) => (hash * 31 + char.charCodeAt(0)) >>> 0, 7)
}

function coverStyle(game) {
  if (game.cover_url) {
    return {
      backgroundImage: `url("${game.cover_url}")`,
      backgroundPosition: 'center',
      backgroundSize: 'cover',
    }
  }

  const hash = hashString(game.name || String(game.id))
  const [base, accent, shadow] = coverPalettes[hash % coverPalettes.length]
  const angle = 120 + (hash % 80)
  return {
    background: `
      radial-gradient(circle at 24% 18%, ${accent}88 0, transparent 30%),
      linear-gradient(${angle}deg, ${base} 0%, ${shadow} 54%, #05080d 100%)
    `,
  }
}

function formatDate(value, language, fallback) {
  if (!value) return fallback
  return new Date(value).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}

export default function GameList({ onSelectGame, mode = 'lounge' }) {
  const { games, setGames, removeGame, updateGame, setLoading } = useGameStore()
  const { language, t } = useI18n()
  const isAdmin = mode === 'admin'
  const [showForm, setShowForm] = React.useState(false)
  const [query, setQuery] = React.useState('')
  const [formData, setFormData] = React.useState({ name: '', description: '' })
  const [editingGame, setEditingGame] = React.useState(null)
  const [editForm, setEditForm] = React.useState({ name: '', description: '' })
  const [uploadingCoverId, setUploadingCoverId] = React.useState(null)

  const filteredGames = React.useMemo(() => {
    const sourceGames = isAdmin ? games : games.filter((game) => game.is_ready)
    const normalized = query.trim().toLowerCase()
    if (!normalized) return sourceGames
    return sourceGames.filter((game) => (
      game.name.toLowerCase().includes(normalized) ||
      (game.description || '').toLowerCase().includes(normalized)
    ))
  }, [games, isAdmin, query])

  const handleCreateGame = async (e) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      toast.error(t('toast.gameNameRequired'))
      return
    }

    setLoading(true)
    try {
      const response = await gamesAPI.create(formData)
      setGames([response.data, ...games])
      setFormData({ name: '', description: '' })
      setShowForm(false)
      toast.success(t('toast.gameCreated'))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.gameCreateFailed')
      toast.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteGame = async (id) => {
    if (!window.confirm(t('toast.gameDeleteConfirm'))) return

    try {
      await gamesAPI.delete(id)
      removeGame(id)
      toast.success(t('toast.gameDeleted'))
    } catch (error) {
      toast.error(t('toast.gameDeleteFailed'))
    }
  }

  const openEditGame = (game) => {
    setEditingGame(game)
    setEditForm({ name: game.name, description: game.description || '' })
  }

  const handleUpdateGame = async (e) => {
    e.preventDefault()
    if (!editForm.name.trim()) {
      toast.error(t('toast.gameNameRequired'))
      return
    }

    try {
      const response = await gamesAPI.update(editingGame.id, editForm)
      updateGame(response.data)
      setEditingGame(null)
      toast.success(t('toast.gameUpdated'))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.gameUpdateFailed')
      toast.error(errorMsg)
    }
  }

  const handleCoverUpload = async (game, file) => {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      toast.error(t('toast.coverType'))
      return
    }

    setUploadingCoverId(game.id)
    try {
      const response = await gamesAPI.uploadCover(game.id, file)
      updateGame(response.data)
      toast.success(t('toast.coverUpdated'))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.coverFailed')
      toast.error(errorMsg)
    } finally {
      setUploadingCoverId(null)
    }
  }

  return (
    <div className="library-shell">
      <aside className="library-sidebar">
        <div className="library-sidebar-title">{isAdmin ? t('game.kitchen') : t('game.lounge')}</div>
        {isAdmin && (
          <button
            onClick={() => setShowForm(true)}
            className="steam-action w-full justify-center"
          >
            <Plus size={18} />
            {t('game.add')}
          </button>
        )}
        <div className="library-stat">
          <span>{isAdmin ? t('game.total') : t('game.ready')}</span>
          <strong>{isAdmin ? games.length : games.filter((game) => game.is_ready).length}</strong>
        </div>
        <div className="library-list">
          {(isAdmin ? games : games.filter((game) => game.is_ready)).slice(0, 12).map((game) => (
            <button key={game.id} onClick={() => onSelectGame(game)}>
              {game.name}
            </button>
          ))}
        </div>
      </aside>

      <section className="library-main">
        <div className="library-toolbar">
          <div>
            <h2>{isAdmin ? t('game.rulebookKitchen') : t('game.choose')}</h2>
            <p>
              {isAdmin
                ? t('game.adminCount', { count: filteredGames.length })
                : t('game.readyCount', { count: filteredGames.length })}
            </p>
          </div>
          <label className="library-search">
            <Search size={18} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('game.search')}
            />
          </label>
        </div>

        {isAdmin && showForm && (
          <form onSubmit={handleCreateGame} className="library-create">
            <input
              type="text"
              placeholder={t('game.name')}
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
            <input
              type="text"
              placeholder={t('game.descriptionOptional')}
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
            <button type="submit" className="steam-action">
              <Plus size={18} />
              {t('game.create')}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="steam-ghost">
              {t('game.cancel')}
            </button>
          </form>
        )}

        {filteredGames.length === 0 ? (
          <div className="empty-library">
            <FileText size={54} />
            <p>{isAdmin ? t('game.noGames') : t('game.noPrepared')}</p>
            {isAdmin && (
              <button onClick={() => setShowForm(true)} className="steam-action">
                <Plus size={18} />
                {t('game.addFirst')}
              </button>
            )}
          </div>
        ) : (
          <div className="game-cover-grid">
            {filteredGames.map((game) => (
              <article key={game.id} className="game-cover-card" onClick={() => onSelectGame(game)}>
                <div className="game-cover-art" style={coverStyle(game)}>
                  <div className="cover-noise"></div>
                  {!game.cover_url && (
                    <>
                      <div className="cover-title">{game.name}</div>
                      <div className="cover-mark">{String(game.name || '?').slice(0, 1).toUpperCase()}</div>
                    </>
                  )}
                </div>
                <div className="game-cover-meta">
                  <div>
                    <h3>{game.name}</h3>
                    <p>
                      {isAdmin
                        ? t('game.rulebookCount', { count: game.rulebook_count || 0, plural: game.rulebook_count === 1 ? '' : 's' })
                        : game.description || t('game.readyForQa')}
                    </p>
                  </div>
                  <div className="cover-date">
                    <CalendarDays size={14} />
                    {formatDate(game.updated_at || game.created_at, language, t('game.recently'))}
                  </div>
                </div>
                {isAdmin && (
                  <>
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        openEditGame(game)
                      }}
                      className="cover-action cover-edit"
                      aria-label={`Edit ${game.name}`}
                    >
                      <Pencil size={16} />
                    </button>
                    <label
                      className="cover-action cover-upload"
                      aria-label={`Upload cover for ${game.name}`}
                      onClick={(event) => event.stopPropagation()}
                    >
                      <Upload size={16} />
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        disabled={uploadingCoverId === game.id}
                        onChange={(event) => {
                          handleCoverUpload(game, event.target.files?.[0])
                          event.target.value = ''
                        }}
                        className="hidden"
                      />
                    </label>
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        handleDeleteGame(game.id)
                      }}
                      className="cover-action cover-delete"
                      aria-label={`Delete ${game.name}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      {editingGame && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/70 px-4 py-8">
          <form onSubmit={handleUpdateGame} className="w-full max-w-xl rounded-lg border border-slate-700 bg-slate-900 shadow-2xl shadow-black/40">
            <div className="flex items-center justify-between border-b border-slate-700 px-6 py-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-100">{t('game.edit')}</h3>
                <p className="text-sm text-slate-500">{t('game.editHelp')}</p>
              </div>
              <button type="button" onClick={() => setEditingGame(null)} className="steam-ghost p-2">
                <X size={18} />
              </button>
            </div>
            <div className="space-y-4 px-6 py-5">
              <label className="block space-y-1">
                <span className="text-sm font-medium text-slate-300">{t('game.nameLabel')}</span>
                <input
                  className="input"
                  value={editForm.name}
                  onChange={(event) => setEditForm({ ...editForm, name: event.target.value })}
                  required
                />
              </label>
              <label className="block space-y-1">
                <span className="text-sm font-medium text-slate-300">{t('game.description')}</span>
                <textarea
                  className="input min-h-28 resize-y"
                  value={editForm.description}
                  onChange={(event) => setEditForm({ ...editForm, description: event.target.value })}
                />
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-700 px-6 py-4">
              <button type="button" onClick={() => setEditingGame(null)} className="steam-ghost">
                {t('game.cancel')}
              </button>
              <button type="submit" className="steam-action">
                <Save size={18} />
                {t('game.save')}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
