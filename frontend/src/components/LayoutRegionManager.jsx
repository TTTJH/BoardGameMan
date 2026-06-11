import React from 'react'
import { ChevronLeft, ChevronRight, Crop, EyeOff, Loader, RotateCcw, Save, Trash2, X, ZoomIn, ZoomOut } from 'lucide-react'
import toast from 'react-hot-toast'
import { assetsAPI, documentsAPI } from '../api/client'
import { useI18n } from '../i18n'

const REGION_TYPES = ['rule', 'setup', 'action', 'scoring', 'example', 'component', 'table', 'variant', 'ignore']

function nextOrder(regions) {
  return regions.reduce((max, region) => Math.max(max, Number(region.reading_order) || 0), 0) + 1
}

function normalizeRegion(region) {
  return {
    ...region,
    localLabel: region.label || '',
  }
}

export default function LayoutRegionManager({ gameId, initialTarget, onClose }) {
  const { t } = useI18n()
  const [documents, setDocuments] = React.useState([])
  const [regions, setRegions] = React.useState([])
  const [documentId, setDocumentId] = React.useState('')
  const [page, setPage] = React.useState(1)
  const [pageImage, setPageImage] = React.useState(null)
  const [pageSize, setPageSize] = React.useState(null)
  const [viewportSize, setViewportSize] = React.useState(null)
  const [zoom, setZoom] = React.useState(1)
  const [selection, setSelection] = React.useState(null)
  const [dragStart, setDragStart] = React.useState(null)
  const [loading, setLoading] = React.useState(false)
  const [saving, setSaving] = React.useState(false)
  const [draft, setDraft] = React.useState({
    label: '',
    region_type: 'rule',
    reading_order: 1,
    enabled: true,
  })
  const imageWrapRef = React.useRef(null)
  const imageViewportRef = React.useRef(null)

  React.useEffect(() => {
    loadInitial()
  }, [gameId])

  React.useEffect(() => {
    if (!initialTarget?.documentId) return
    setDocumentId(String(initialTarget.documentId))
    setPage(Math.max(1, Number(initialTarget.page) || 1))
  }, [initialTarget?.nonce])

  React.useEffect(() => {
    if (!documentId) return
    loadPage()
    loadRegions()
  }, [documentId, page])

  React.useEffect(() => {
    const node = imageViewportRef.current
    if (!node) return undefined

    const updateSize = () => {
      setViewportSize({
        width: node.clientWidth,
        height: node.clientHeight,
      })
    }
    updateSize()

    const observer = new ResizeObserver(updateSize)
    observer.observe(node)
    window.addEventListener('resize', updateSize)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', updateSize)
    }
  }, [pageImage])

  React.useEffect(() => {
    setDraft((current) => ({
      ...current,
      reading_order: nextOrder(regions),
    }))
  }, [regions])

  const loadInitial = async () => {
    setLoading(true)
    try {
      const response = await documentsAPI.list(gameId)
      setDocuments(response.data)
      if (response.data.length > 0) {
        const targetDocument = response.data.find((doc) => doc.id === Number(initialTarget?.documentId))
        setDocumentId(String(targetDocument?.id || response.data[0].id))
        setPage(targetDocument ? Math.max(1, Number(initialTarget?.page) || 1) : 1)
      }
    } catch (error) {
      toast.error(t('toast.layoutLoadFailed'))
    } finally {
      setLoading(false)
    }
  }

  const loadPage = async () => {
    setPageImage(null)
    setPageSize(null)
    setSelection(null)
    try {
      const response = await assetsAPI.pagePreview(gameId, Number(documentId), Number(page))
      setPageImage(response.data.image_url)
    } catch (error) {
      toast.error(t('toast.assetPageFailed'))
    }
  }

  const loadRegions = async () => {
    try {
      const response = await documentsAPI.listLayoutRegions(Number(documentId), { page: Number(page) })
      setRegions(response.data.map(normalizeRegion))
    } catch (error) {
      toast.error(t('toast.layoutLoadFailed'))
    }
  }

  const selectedDocument = documents.find((doc) => doc.id === Number(documentId))
  const maxPage = selectedDocument?.pages || 1
  const currentPage = Math.min(maxPage, Math.max(1, Number(page) || 1))

  const changePage = (nextPage) => {
    setPage(Math.min(maxPage, Math.max(1, nextPage)))
  }

  const changeZoom = (nextZoom) => {
    setZoom(Math.min(2.5, Math.max(0.4, nextZoom)))
  }

  const fitScale = React.useMemo(() => {
    if (!pageSize || !viewportSize?.width) return 1
    const availableWidth = Math.max(320, viewportSize.width - 24)
    const scale = availableWidth / pageSize.width
    return Math.min(2, Math.max(0.1, scale))
  }, [pageSize, viewportSize])

  const imageDisplayStyle = pageSize
    ? { width: `${pageSize.width * fitScale * zoom}px`, maxWidth: 'none' }
    : undefined

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

  const saveRegion = async (override = {}) => {
    if (!documentId || !pageImage || !selection) {
      toast.error(t('toast.layoutSelectFirst'))
      return
    }
    if (selection.width < 0.01 || selection.height < 0.01) {
      toast.error(t('toast.assetTooSmall'))
      return
    }

    setSaving(true)
    try {
      const response = await documentsAPI.createLayoutRegion(Number(documentId), {
        page: Number(page),
        label: override.label !== undefined ? override.label : (draft.label.trim() || null),
        region_type: override.region_type || draft.region_type,
        reading_order: Number(draft.reading_order) || nextOrder(regions),
        enabled: override.enabled ?? draft.enabled,
        bbox: selection,
      })
      setRegions((current) => [...current, normalizeRegion(response.data)].sort(regionSort))
      setSelection(null)
      setDraft({
        label: '',
        region_type: 'rule',
        reading_order: nextOrder([...regions, response.data]),
        enabled: true,
      })
      toast.success(t('toast.layoutSaved'))
    } catch (error) {
      const detail = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.layoutSaveFailed')
      toast.error(detail)
    } finally {
      setSaving(false)
    }
  }

  const updateRegion = async (region, patch = {}) => {
    const next = { ...region, ...patch }
    setRegions((current) => current.map((item) => (item.id === region.id ? next : item)).sort(regionSort))
    try {
      const response = await documentsAPI.updateLayoutRegion(region.id, {
        label: next.localLabel?.trim() || null,
        region_type: next.region_type,
        reading_order: Number(next.reading_order) || 1,
        enabled: next.enabled,
        bbox: next.bbox,
      })
      setRegions((current) => current.map((item) => (item.id === region.id ? normalizeRegion(response.data) : item)).sort(regionSort))
      toast.success(t('toast.layoutUpdated'))
    } catch (error) {
      toast.error(t('toast.layoutUpdateFailed'))
      await loadRegions()
    }
  }

  const deleteRegion = async (region) => {
    if (!window.confirm(t('layout.deleteConfirm', { label: region.label || `#${region.reading_order}` }))) return
    try {
      await documentsAPI.deleteLayoutRegion(region.id)
      setRegions((current) => current.filter((item) => item.id !== region.id))
      toast.success(t('toast.layoutDeleted'))
    } catch (error) {
      toast.error(t('toast.layoutDeleteFailed'))
    }
  }

  const applySelectionToRegion = async (region) => {
    if (!selection) {
      toast.error(t('toast.layoutSelectFirst'))
      return
    }
    await updateRegion(region, { bbox: selection })
    setSelection(null)
  }

  return (
    <div className="rounded-md border border-slate-700/80 bg-slate-900/80 p-4 shadow-xl shadow-black/25">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-sky-300">{t('layout.eyebrow')}</p>
          <h3 className="text-lg font-semibold text-slate-100">{t('layout.title')}</h3>
          <p className="mt-1 text-sm text-slate-500">{t('layout.desc')}</p>
          <p className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
            {t('layout.reprocessNotice')}
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
          {t('layout.loading')}
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.85fr)]">
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
                  {pageSize ? t('assets.imageSize', { width: pageSize.width, height: pageSize.height }) : t('assets.preview')}
                </p>
                <div className="flex items-center gap-2 rounded border border-slate-700 bg-slate-950/70 px-2 py-1">
                  <button type="button" onClick={() => changeZoom(zoom - 0.1)} className="rounded p-1 text-slate-300 transition hover:bg-slate-800" title={t('assets.zoomOut')}>
                    <ZoomOut size={16} />
                  </button>
                  <input
                    type="range"
                    min="0.4"
                    max="2.5"
                    step="0.05"
                    value={zoom}
                    onChange={(event) => changeZoom(Number(event.target.value))}
                    className="w-28 accent-sky-400"
                    aria-label={t('assets.zoom')}
                  />
                  <button type="button" onClick={() => changeZoom(zoom + 0.1)} className="rounded p-1 text-slate-300 transition hover:bg-slate-800" title={t('assets.zoomIn')}>
                    <ZoomIn size={16} />
                  </button>
                  <button type="button" onClick={() => changeZoom(1)} className="rounded px-2 py-1 text-xs text-slate-300 transition hover:bg-slate-800" title={t('assets.resetZoom')}>
                    <RotateCcw size={14} />
                    {Math.round(zoom * 100)}%
                  </button>
                </div>
              </div>
              {pageImage ? (
                <div ref={imageViewportRef} className="max-h-[760px] overflow-auto rounded border border-slate-700 bg-slate-950 p-3">
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
                      style={imageDisplayStyle}
                      draggable="false"
                      onLoad={(event) => setPageSize({
                        width: event.currentTarget.naturalWidth,
                        height: event.currentTarget.naturalHeight,
                      })}
                    />
                    {regions.map((region) => (
                      <RegionOverlay key={region.id} region={region} t={t} />
                    ))}
                    {selection && (
                      <div
                        className="pointer-events-none absolute border-2 border-sky-300 bg-sky-400/20 shadow-[0_0_0_9999px_rgba(2,6,23,0.30)]"
                        style={bboxStyle(selection)}
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
                <Crop size={16} />
                {t('layout.newRegion')}
              </div>
              <div className="space-y-2">
                <input
                  value={draft.label}
                  onChange={(event) => setDraft({ ...draft, label: event.target.value })}
                  placeholder={t('layout.labelPlaceholder')}
                  className="input px-3 py-2 text-sm"
                />
                <div className="grid grid-cols-[minmax(0,1fr)_96px] gap-2">
                  <select
                    value={draft.region_type}
                    onChange={(event) => setDraft({ ...draft, region_type: event.target.value })}
                    className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
                  >
                    {REGION_TYPES.map((type) => (
                      <option key={type} value={type}>{t(`layoutType.${type}`)}</option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min="1"
                    value={draft.reading_order}
                    onChange={(event) => setDraft({ ...draft, reading_order: Number(event.target.value) || 1 })}
                    className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                    aria-label={t('layout.order')}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-400">
                  <input
                    type="checkbox"
                    checked={draft.enabled}
                    onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
                  />
                  {t('layout.enabled')}
                </label>
                {draft.region_type === 'ignore' && (
                  <p className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                    {t('layout.ignoreHint')}
                  </p>
                )}
                <div className="grid gap-2 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => saveRegion()}
                    disabled={saving}
                    className="steam-action disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {saving ? <Loader size={18} className="animate-spin" /> : <Save size={18} />}
                    {t('layout.saveSelected')}
                  </button>
                  <button
                    type="button"
                    onClick={() => saveRegion({ region_type: 'ignore', label: draft.label.trim() || t('layout.ignoreLabel') })}
                    disabled={saving}
                    className="steam-ghost disabled:cursor-not-allowed disabled:opacity-50"
                    title={t('layout.saveIgnoredTitle')}
                  >
                    {saving ? <Loader size={18} className="animate-spin" /> : <EyeOff size={18} />}
                    {t('layout.saveIgnored')}
                  </button>
                </div>
              </div>
            </div>

            <div className="rounded border border-slate-700 bg-slate-950/40 p-3">
              <h4 className="mb-3 text-sm font-semibold text-slate-200">{t('layout.savedRegions')}</h4>
              <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
                {regions.length === 0 ? (
                  <p className="text-sm text-slate-500">{t('layout.empty')}</p>
                ) : regions.map((region) => (
                  <RegionEditor
                    key={region.id}
                    region={region}
                    onLocalChange={(patch) => {
                      setRegions((current) => current.map((item) => (
                        item.id === region.id ? { ...item, ...patch } : item
                      )))
                    }}
                    onSave={updateRegion}
                    onApplySelection={applySelectionToRegion}
                    onDelete={deleteRegion}
                    hasSelection={Boolean(selection)}
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

function regionSort(left, right) {
  return (Number(left.reading_order) || 1) - (Number(right.reading_order) || 1) || left.id - right.id
}

function bboxStyle(bbox) {
  return {
    left: `${bbox.x * 100}%`,
    top: `${bbox.y * 100}%`,
    width: `${bbox.width * 100}%`,
    height: `${bbox.height * 100}%`,
  }
}

function RegionOverlay({ region, t }) {
  const enabledClass = region.region_type === 'ignore'
    ? 'border-amber-300 bg-amber-400/20'
    : region.enabled
    ? 'border-emerald-300 bg-emerald-400/15'
    : 'border-slate-500 bg-slate-500/10'
  return (
    <div
      className={`pointer-events-none absolute border-2 ${enabledClass}`}
      style={bboxStyle(region.bbox)}
    >
      <div className="absolute left-0 top-0 max-w-full rounded-br bg-slate-950/90 px-2 py-1 text-[11px] font-semibold text-slate-100">
        {region.reading_order}. {region.label || t(`layoutType.${region.region_type}`)}
      </div>
    </div>
  )
}

function RegionEditor({ region, onLocalChange, onSave, onApplySelection, onDelete, hasSelection, t }) {
  return (
    <div className="rounded border border-slate-700 bg-slate-900/80 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="rounded bg-slate-950 px-2 py-1 text-xs font-semibold text-sky-200">#{region.reading_order}</span>
        <label className="flex items-center gap-1 text-xs text-slate-400">
          <input
            type="checkbox"
            checked={region.enabled}
            onChange={(event) => onLocalChange({ enabled: event.target.checked })}
          />
          {t('layout.enabled')}
        </label>
      </div>
      <div className="space-y-2">
        <input
          value={region.localLabel || ''}
          onChange={(event) => onLocalChange({ localLabel: event.target.value })}
          className="input px-2 py-1 text-xs"
          placeholder={t('layout.labelPlaceholder')}
        />
        <div className="grid grid-cols-[minmax(0,1fr)_90px] gap-2">
          <select
            value={region.region_type}
            onChange={(event) => onLocalChange({ region_type: event.target.value })}
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
          >
            {REGION_TYPES.map((type) => (
              <option key={type} value={type}>{t(`layoutType.${type}`)}</option>
            ))}
          </select>
          <input
            type="number"
            min="1"
            value={region.reading_order}
            onChange={(event) => onLocalChange({ reading_order: Number(event.target.value) || 1 })}
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100"
            aria-label={t('layout.order')}
          />
        </div>
        <p className="text-[11px] text-slate-500">
          {t('layout.bboxSummary', {
            x: Math.round(region.bbox.x * 100),
            y: Math.round(region.bbox.y * 100),
            width: Math.round(region.bbox.width * 100),
            height: Math.round(region.bbox.height * 100),
          })}
        </p>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => onSave(region)} className="steam-ghost px-2 py-1 text-xs">
            <Save size={14} />
            {t('chunks.save')}
          </button>
          <button
            type="button"
            onClick={() => onApplySelection(region)}
            disabled={!hasSelection}
            className="steam-ghost px-2 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Crop size={14} />
            {t('layout.useSelection')}
          </button>
          <button type="button" onClick={() => onDelete(region)} className="btn-danger px-2 py-1 text-xs">
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
