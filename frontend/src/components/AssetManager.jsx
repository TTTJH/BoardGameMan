import React from 'react'
import { ChevronLeft, ChevronRight, ImagePlus, Loader, RefreshCw, RotateCcw, Save, Trash2, X, ZoomIn, ZoomOut } from 'lucide-react'
import toast from 'react-hot-toast'
import { assetsAPI, documentsAPI } from '../api/client'
import { useI18n } from '../i18n'

const ASSET_TYPES = ['icon', 'token', 'tile', 'card', 'board', 'component', 'reference']

function splitKeywords(value = '') {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function keywordText(asset) {
  return (asset.keywords || []).join(', ')
}

export default function AssetManager({ gameId, onClose }) {
  const { t } = useI18n()
  const [documents, setDocuments] = React.useState([])
  const [assets, setAssets] = React.useState([])
  const [documentId, setDocumentId] = React.useState('')
  const [page, setPage] = React.useState(1)
  const [pageImage, setPageImage] = React.useState(null)
  const [pageSize, setPageSize] = React.useState(null)
  const [previewScale, setPreviewScale] = React.useState({ render: 1, base: 1 })
  const [zoom, setZoom] = React.useState(0.9)
  const [selection, setSelection] = React.useState(null)
  const [draft, setDraft] = React.useState({
    name: '',
    display_name: '',
    asset_type: 'component',
    keywords: '',
    enabled: true,
  })
  const [loading, setLoading] = React.useState(false)
  const [saving, setSaving] = React.useState(false)
  const [regenerating, setRegenerating] = React.useState(false)
  const [regeneratingAssetIds, setRegeneratingAssetIds] = React.useState([])
  const [dragStart, setDragStart] = React.useState(null)
  const imageWrapRef = React.useRef(null)

  React.useEffect(() => {
    loadInitial()
  }, [gameId])

  React.useEffect(() => {
    if (documentId) {
      loadPage()
    }
  }, [documentId, page])

  const loadInitial = async () => {
    setLoading(true)
    try {
      const [docsResponse, assetsResponse] = await Promise.all([
        documentsAPI.list(gameId),
        assetsAPI.list(gameId),
      ])
      setDocuments(docsResponse.data)
      setAssets(assetsResponse.data)
      if (docsResponse.data.length > 0) {
        setDocumentId(String(docsResponse.data[0].id))
        setPage(1)
      }
    } catch (error) {
      toast.error(t('toast.assetsLoadFailed'))
    } finally {
      setLoading(false)
    }
  }

  const loadAssets = async () => {
    const response = await assetsAPI.list(gameId)
    setAssets(response.data)
    return response.data
  }

  const loadPage = async () => {
    setPageImage(null)
    setPageSize(null)
    setPreviewScale({ render: 1, base: 1 })
    setSelection(null)
    try {
      const response = await assetsAPI.pagePreview(gameId, Number(documentId), Number(page))
      setPreviewScale({
        render: Number(response.data.render_scale) || 1,
        base: Number(response.data.base_scale) || Number(response.data.render_scale) || 1,
      })
      setPageImage(response.data.image_url)
    } catch (error) {
      toast.error(t('toast.assetPageFailed'))
    }
  }

  const selectedDocument = documents.find((doc) => doc.id === Number(documentId))
  const maxPage = selectedDocument?.pages || 1
  const currentPage = Math.min(maxPage, Math.max(1, Number(page) || 1))
  const changePage = (nextPage) => {
    setPage(Math.min(maxPage, Math.max(1, nextPage)))
  }
  const changeZoom = (nextZoom) => {
    setZoom(Math.min(2.5, Math.max(0.45, nextZoom)))
  }

  const pointFromEvent = (event) => {
    const rect = imageWrapRef.current?.getBoundingClientRect()
    if (!rect) return null
    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width))
    const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height))
    return { x, y }
  }

  const handlePointerDown = (event) => {
    if (!pageImage) return
    const point = pointFromEvent(event)
    if (!point) return
    setDragStart(point)
    setSelection({ x: point.x, y: point.y, width: 0, height: 0 })
  }

  const handlePointerMove = (event) => {
    if (!dragStart) return
    const point = pointFromEvent(event)
    if (!point) return
    const x = Math.min(dragStart.x, point.x)
    const y = Math.min(dragStart.y, point.y)
    const width = Math.abs(point.x - dragStart.x)
    const height = Math.abs(point.y - dragStart.y)
    setSelection({ x, y, width, height })
  }

  const handlePointerUp = () => {
    setDragStart(null)
  }

  const saveAsset = async () => {
    if (!documentId || !pageImage || !selection) {
      toast.error(t('toast.assetSelectFirst'))
      return
    }
    if (selection.width < 0.01 || selection.height < 0.01) {
      toast.error(t('toast.assetTooSmall'))
      return
    }
    if (!draft.name.trim()) {
      toast.error(t('toast.assetNameRequired'))
      return
    }

    setSaving(true)
    try {
      const response = await assetsAPI.create(gameId, {
        document_id: Number(documentId),
        page: Number(page),
        name: draft.name.trim(),
        display_name: draft.display_name.trim() || null,
        asset_type: draft.asset_type,
        keywords: splitKeywords(draft.keywords),
        enabled: draft.enabled,
        bbox: selection,
      })
      setAssets([response.data, ...assets])
      setSelection(null)
      setDraft({
        name: '',
        display_name: '',
        asset_type: 'component',
        keywords: '',
        enabled: true,
      })
      toast.success(t('toast.assetSaved'))
    } catch (error) {
      const detail = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.assetSaveFailed')
      toast.error(detail)
    } finally {
      setSaving(false)
    }
  }

  const updateAsset = async (asset, patch) => {
    const next = { ...asset, ...patch }
    setAssets((current) => current.map((item) => (item.id === asset.id ? next : item)))
    try {
      const response = await assetsAPI.update(asset.id, {
        name: next.name,
        display_name: next.display_name || null,
        asset_type: next.asset_type,
        keywords: Array.isArray(next.keywords) ? next.keywords : splitKeywords(next.keywordInput || ''),
        enabled: next.enabled,
      })
      setAssets((current) => current.map((item) => (item.id === asset.id ? response.data : item)))
      toast.success(t('toast.assetUpdated'))
    } catch (error) {
      toast.error(t('toast.assetUpdateFailed'))
      await loadInitial()
    }
  }

  const deleteAsset = async (asset) => {
    if (!window.confirm(t('assets.deleteConfirm', { name: asset.name }))) return
    try {
      await assetsAPI.delete(asset.id)
      setAssets((current) => current.filter((item) => item.id !== asset.id))
      toast.success(t('toast.assetDeleted'))
    } catch (error) {
      toast.error(t('toast.assetDeleteFailed'))
    }
  }

  const regenerateAllAssets = async () => {
    if (regenerating || assets.length === 0) return
    setRegenerating(true)
    try {
      const response = await assetsAPI.regenerate(gameId)
      await loadAssets()
      toast.success(t('toast.assetsRegenerated', { count: response.data.count || 0 }))
      if (response.data.failed_count > 0) {
        toast.error(t('toast.assetsRegeneratePartial', { count: response.data.failed_count }))
      }
    } catch (error) {
      toast.error(t('toast.assetsRegenerateFailed'))
    } finally {
      setRegenerating(false)
    }
  }

  const regenerateOneAsset = async (asset) => {
    if (regeneratingAssetIds.includes(asset.id)) return
    setRegeneratingAssetIds((current) => [...current, asset.id])
    try {
      const response = await assetsAPI.regenerateOne(asset.id)
      setAssets((current) => current.map((item) => (item.id === asset.id ? response.data : item)))
      toast.success(t('toast.assetRegenerated'))
    } catch (error) {
      const detail = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.assetsRegenerateFailed')
      toast.error(detail)
    } finally {
      setRegeneratingAssetIds((current) => current.filter((id) => id !== asset.id))
    }
  }

  return (
    <div className="rounded-md border border-slate-700/80 bg-slate-900/80 p-4 shadow-xl shadow-black/25">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-sky-300">{t('assets.eyebrow')}</p>
          <h3 className="text-lg font-semibold text-slate-100">{t('assets.title')}</h3>
          <p className="mt-1 text-sm text-slate-500">
            {t('assets.desc')}
          </p>
          <p className="mt-1 text-xs text-sky-200/70">
            {t('assets.hdNotice')}
          </p>
        </div>
        <button type="button" onClick={onClose} className="steam-ghost px-3 py-1 text-xs">
          <X size={16} />
          {t('assets.close')}
        </button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Loader size={16} className="animate-spin" />
          {t('assets.loading')}
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(360px,0.8fr)]">
          <div className="space-y-3">
            <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
              <select
                value={documentId}
                onChange={(event) => {
                  setDocumentId(event.target.value)
                  setPage(1)
                }}
                className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
              >
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>{doc.filename}</option>
                ))}
              </select>
              <div className="flex flex-wrap items-center gap-2 rounded border border-slate-700 bg-slate-950/70 px-2 py-1">
                <button
                  type="button"
                  onClick={() => changePage(currentPage - 1)}
                  disabled={currentPage <= 1}
                  className="rounded p-1 text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
                  title={t('assets.prevPage')}
                >
                  <ChevronLeft size={18} />
                </button>
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  {t('assets.page')}
                  <input
                    type="number"
                    min="1"
                    max={maxPage}
                    value={currentPage}
                    onChange={(event) => changePage(Number(event.target.value) || 1)}
                    className="w-16 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-center text-sm text-slate-100"
                  />
                  <span>{t('assets.pageTotal', { total: maxPage })}</span>
                </label>
                <button
                  type="button"
                  onClick={() => changePage(currentPage + 1)}
                  disabled={currentPage >= maxPage}
                  className="rounded p-1 text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
                  title={t('assets.nextPage')}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>

            <div className="rounded border border-slate-700 bg-slate-950/40 p-3">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-slate-500">
                  {pageSize
                    ? t('assets.hdPreviewSize', { width: pageSize.naturalWidth, height: pageSize.naturalHeight })
                    : t('assets.preview')}
                </p>
                <div className="flex items-center gap-2 rounded border border-slate-700 bg-slate-950/70 px-2 py-1">
                  <button
                    type="button"
                    onClick={() => changeZoom(zoom - 0.1)}
                    className="rounded p-1 text-slate-300 transition hover:bg-slate-800"
                    title={t('assets.zoomOut')}
                  >
                    <ZoomOut size={16} />
                  </button>
                  <input
                    type="range"
                    min="0.45"
                    max="2.5"
                    step="0.05"
                    value={zoom}
                    onChange={(event) => changeZoom(Number(event.target.value))}
                    className="w-28 accent-sky-400"
                    aria-label={t('assets.zoom')}
                  />
                  <button
                    type="button"
                    onClick={() => changeZoom(zoom + 0.1)}
                    className="rounded p-1 text-slate-300 transition hover:bg-slate-800"
                    title={t('assets.zoomIn')}
                  >
                    <ZoomIn size={16} />
                  </button>
                  <button
                    type="button"
                    onClick={() => changeZoom(0.9)}
                    className="rounded px-2 py-1 text-xs text-slate-300 transition hover:bg-slate-800"
                    title={t('assets.resetZoom')}
                  >
                    <RotateCcw size={14} />
                    {Math.round(zoom * 100)}%
                  </button>
                </div>
              </div>
              {pageImage ? (
                <div className="max-h-[760px] overflow-auto rounded border border-slate-700 bg-slate-950 p-3">
                  <div
                    ref={imageWrapRef}
                    className="relative mx-auto w-fit overflow-hidden rounded bg-slate-950"
                    onPointerDown={handlePointerDown}
                    onPointerMove={handlePointerMove}
                    onPointerUp={handlePointerUp}
                    onPointerLeave={handlePointerUp}
                  >
                    <img
                      src={pageImage}
                      alt={t('assets.pagePreviewAlt')}
                      className="select-none object-contain"
                      style={pageSize ? { width: `${pageSize.width * zoom}px`, maxWidth: 'none' } : undefined}
                      draggable="false"
                      onLoad={(event) => {
                        const naturalWidth = event.currentTarget.naturalWidth
                        const naturalHeight = event.currentTarget.naturalHeight
                        const displayRatio = previewScale.render > 0
                          ? previewScale.base / previewScale.render
                          : 1
                        setPageSize({
                          width: Math.round(naturalWidth * displayRatio),
                          height: Math.round(naturalHeight * displayRatio),
                          naturalWidth,
                          naturalHeight,
                        })
                      }}
                    />
                    {selection && (
                      <div
                        className="pointer-events-none absolute border-2 border-sky-300 bg-sky-400/20 shadow-[0_0_0_9999px_rgba(2,6,23,0.45)]"
                        style={{
                          left: `${selection.x * 100}%`,
                          top: `${selection.y * 100}%`,
                          width: `${selection.width * 100}%`,
                          height: `${selection.height * 100}%`,
                        }}
                      />
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex min-h-48 items-center justify-center text-sm text-slate-500">
                  {t('assets.selectPage')}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <div className="rounded border border-slate-700 bg-slate-950/40 p-3">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                <ImagePlus size={16} />
                {t('assets.newAsset')}
              </div>
              <div className="space-y-2">
                <input
                  value={draft.name}
                  onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                  placeholder={t('assets.namePlaceholder')}
                  className="input px-3 py-2 text-sm"
                />
                <input
                  value={draft.display_name}
                  onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
                  placeholder={t('assets.displayNamePlaceholder')}
                  className="input px-3 py-2 text-sm"
                />
                <select
                  value={draft.asset_type}
                  onChange={(event) => setDraft({ ...draft, asset_type: event.target.value })}
                  className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
                >
                  {ASSET_TYPES.map((type) => (
                    <option key={type} value={type}>{t(`assetType.${type}`)}</option>
                  ))}
                </select>
                <textarea
                  value={draft.keywords}
                  onChange={(event) => setDraft({ ...draft, keywords: event.target.value })}
                  placeholder={t('assets.keywordsPlaceholder')}
                  className="input min-h-20 resize-y px-3 py-2 text-sm"
                />
                <label className="flex items-center gap-2 text-sm text-slate-400">
                  <input
                    type="checkbox"
                    checked={draft.enabled}
                    onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
                  />
                  {t('eval.enabled')}
                </label>
                <button
                  type="button"
                  onClick={saveAsset}
                  disabled={saving}
                  className="steam-action w-full disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving ? <Loader size={18} className="animate-spin" /> : <Save size={18} />}
                  {t('assets.saveSelected')}
                </button>
              </div>
            </div>

            <div className="rounded border border-slate-700 bg-slate-950/40 p-3">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-sm font-semibold text-slate-200">{t('assets.savedAssets')}</h4>
                <button
                  type="button"
                  onClick={regenerateAllAssets}
                  disabled={regenerating || assets.length === 0}
                  className="steam-ghost px-2 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  title={t('assets.regenerateHdTitle')}
                >
                  {regenerating ? <Loader size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                  {t('assets.regenerateHd')}
                </button>
              </div>
              <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
                {assets.length === 0 ? (
                  <p className="text-sm text-slate-500">{t('assets.empty')}</p>
                ) : assets.map((asset) => (
                  <AssetEditor
                    key={asset.id}
                    asset={asset}
                    onUpdate={updateAsset}
                    onDelete={deleteAsset}
                    onRegenerate={regenerateOneAsset}
                    regenerating={regeneratingAssetIds.includes(asset.id)}
                    t={t}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function AssetEditor({ asset, onUpdate, onDelete, onRegenerate, regenerating, t }) {
  const [local, setLocal] = React.useState({
    ...asset,
    keywordInput: keywordText(asset),
  })

  React.useEffect(() => {
    setLocal({ ...asset, keywordInput: keywordText(asset) })
  }, [asset])

  return (
    <div className="rounded border border-slate-700 bg-slate-900/80 p-2">
      <div className="grid gap-2 sm:grid-cols-[96px_minmax(0,1fr)]">
        <a href={asset.image_url} target="_blank" rel="noreferrer" className="block">
          <img
            src={asset.image_url}
            alt={asset.display_name || asset.name}
            className="h-24 w-full rounded border border-slate-700 bg-slate-950 object-contain"
            loading="lazy"
          />
        </a>
        <div className="space-y-2">
          <input
            value={local.name}
            onChange={(event) => setLocal({ ...local, name: event.target.value })}
            className="input px-2 py-1 text-xs"
          />
          <input
            value={local.display_name || ''}
            onChange={(event) => setLocal({ ...local, display_name: event.target.value })}
            className="input px-2 py-1 text-xs"
            placeholder={t('assets.displayName')}
          />
          <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
            <select
              value={local.asset_type}
              onChange={(event) => setLocal({ ...local, asset_type: event.target.value })}
              className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
            >
              {ASSET_TYPES.map((type) => (
                <option key={type} value={type}>{t(`assetType.${type}`)}</option>
              ))}
            </select>
            <label className="flex items-center gap-1 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={local.enabled}
                onChange={(event) => setLocal({ ...local, enabled: event.target.checked })}
              />
              {t('eval.enabled')}
            </label>
          </div>
          <textarea
            value={local.keywordInput}
            onChange={(event) => setLocal({ ...local, keywordInput: event.target.value })}
            className="input min-h-14 resize-y px-2 py-1 text-xs"
          />
          <p className="text-[11px] text-slate-500">
            {t('eval.page')} {asset.page || '-'} · {asset.asset_type}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onUpdate(asset, {
                ...local,
                keywords: splitKeywords(local.keywordInput),
              })}
              className="steam-ghost px-2 py-1 text-xs"
            >
              <Save size={14} />
              {t('chunks.save')}
            </button>
            <button
              type="button"
              onClick={() => onRegenerate(asset)}
              disabled={regenerating || !asset.source_bbox}
              className="steam-ghost px-2 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
              title={t('assets.regenerateOneHdTitle')}
            >
              {regenerating ? <Loader size={14} className="animate-spin" /> : <RefreshCw size={14} />}
              {t('assets.hd')}
            </button>
            <button
              type="button"
              onClick={() => onDelete(asset)}
              className="btn-danger px-2 py-1 text-xs"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
