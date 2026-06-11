import React from 'react'
import { ArrowLeft, Crop, Image } from 'lucide-react'
import DocumentUpload from './DocumentUpload'
import ChatBox from './ChatBox'
import AssetManager from './AssetManager'
import LayoutRegionManager from './LayoutRegionManager'
import { useI18n } from '../i18n'

export default function GameDetail({ game, onBack, mode = 'lounge' }) {
  const isAdmin = mode === 'admin'
  const { t } = useI18n()
  const [showAssets, setShowAssets] = React.useState(false)
  const [showLayout, setShowLayout] = React.useState(false)
  const [layoutTarget, setLayoutTarget] = React.useState(null)

  const openLayoutAt = React.useCallback((target) => {
    setLayoutTarget({ ...target, nonce: Date.now() })
    setShowLayout(true)
  }, [])

  return (
    <div className="space-y-6">
      <button
        onClick={onBack}
        className="steam-ghost"
      >
        <ArrowLeft size={20} />
        {isAdmin ? t('detail.backKitchen') : t('detail.backGames')}
      </button>

      <div className="rounded-md border border-slate-700/70 bg-slate-900/70 p-5 shadow-lg shadow-black/20">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-sky-300">
              {isAdmin ? t('detail.preparing') : t('detail.askRulebook')}
            </p>
            <h2 className="mt-1 text-3xl font-black text-slate-100">{game.name}</h2>
            {game.description && (
              <p className="mt-2 max-w-3xl text-sm text-slate-400">{game.description}</p>
            )}
          </div>
          {isAdmin && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setShowLayout((current) => !current)}
                className={showLayout ? 'steam-action' : 'steam-ghost'}
              >
                <Crop size={18} />
                {t('layout.manageButton')}
              </button>
              <button
                type="button"
                onClick={() => setShowAssets((current) => !current)}
                className={showAssets ? 'steam-action' : 'steam-ghost'}
              >
                <Image size={18} />
                {t('assets.manageButton')}
              </button>
            </div>
          )}
        </div>
      </div>

      {isAdmin && showAssets && (
        <AssetManager gameId={game.id} onClose={() => setShowAssets(false)} />
      )}

      {isAdmin && showLayout && (
        <LayoutRegionManager
          gameId={game.id}
          initialTarget={layoutTarget}
          onClose={() => setShowLayout(false)}
        />
      )}

      <div className={isAdmin ? 'grid grid-cols-1 lg:grid-cols-3 gap-6' : 'grid grid-cols-1'}>
        {isAdmin && (
          <div className="lg:col-span-1">
            <DocumentUpload gameId={game.id} onOpenLayout={openLayoutAt} />
          </div>
        )}

        <div className={isAdmin ? 'lg:col-span-2' : ''}>
          <ChatBox gameId={game.id} gameName={game.name} />
        </div>
      </div>
    </div>
  )
}
