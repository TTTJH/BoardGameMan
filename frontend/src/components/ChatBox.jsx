import React from 'react'
import { ArrowUp, BookOpenText, Compass, Loader, RotateCcw, Send, Trash2, X, ZoomIn, ZoomOut } from 'lucide-react'
import { useChatStore } from '../store'
import { chatAPI, glossaryAPI } from '../api/client'
import toast from 'react-hot-toast'
import ReactMarkdown from 'react-markdown'
import { useI18n } from '../i18n'

const SHOW_GLOSSARY_CHIPS = false

function isBeginnerPrompt(message = '') {
  return [
    'first-play onboarding guide',
    '新手开荒视角',
    '初回プレイ向け',
    '첫 플레이 입문',
  ].some((pattern) => message.includes(pattern))
}

function SourceItem({ source, onOpenImage }) {
  const { t } = useI18n()

  if (typeof source === 'string') {
    return (
      <li
        className="rounded-md border border-slate-700/70 bg-slate-950/30 px-2 py-1.5 text-xs text-slate-400"
        title={source}
      >
        <span className="line-clamp-2">{source}</span>
      </li>
    )
  }

  const sourceLabel = source.source_type
    ? t(`sourceType.${source.source_type}`)
    : (source.source_label || t('chat.rulebookSource'))

  const imageTitle = source.page ? `${t('chat.rulebookPage')} ${source.page}` : t('chat.rulebookPage')
  const title = source.filename
    ? `${source.filename}${source.page ? ` - ${t('eval.page')} ${source.page}` : ''}`
    : imageTitle
  const subtitle = `${sourceLabel}${source.page ? ` - ${t('eval.page')} ${source.page}` : ''}`
  const content = (
    <>
      {source.image_url ? (
        <div className="h-12 overflow-hidden bg-slate-950 sm:h-14">
          <img
            src={source.image_url}
            alt={imageTitle}
            className="h-full w-full object-contain"
            loading="lazy"
          />
        </div>
      ) : (
        <div className="flex h-12 items-center justify-center bg-slate-950/60 px-1 text-center text-[10px] text-slate-500 sm:h-14">
          {source.page ? `${t('eval.page')} ${source.page}` : t('chat.rulebookSource')}
        </div>
      )}
      <div className="space-y-0.5 px-1.5 py-1">
        <p className="truncate text-[10px] font-semibold leading-tight text-slate-200">
          {source.page ? `${t('eval.page')} ${source.page}` : t('chat.rulebookSource')}
        </p>
        <p className="truncate text-[9px] leading-tight text-slate-500">{sourceLabel}</p>
        {source.excerpt && !source.image_url && (
          <p className="line-clamp-1 text-[9px] leading-tight text-slate-400">{source.excerpt}</p>
        )}
      </div>
    </>
  )

  return (
    <li
      className="overflow-hidden rounded-md border border-slate-700/70 bg-slate-950/30"
      title={[title, subtitle, source.excerpt].filter(Boolean).join('\n\n')}
    >
      {source.image_url ? (
        <button
          type="button"
          onClick={() => onOpenImage?.({
            url: source.image_url,
            title: imageTitle,
            subtitle: source.filename ? `${source.filename}${source.page ? ` - ${t('eval.page')} ${source.page}` : ''}` : '',
            highlightRegions: source.highlight_regions || [],
          })}
          className="block h-full w-full text-left transition hover:bg-slate-800/50 focus:outline-none focus:ring-2 focus:ring-sky-400"
          aria-label={imageTitle}
          title={imageTitle}
        >
          {content}
        </button>
      ) : (
        <div>{content}</div>
      )}
    </li>
  )
}

function SourceGrid({ sources = [], onOpenImage }) {
  if (!sources?.length) return null
  return (
    <ul className="grid grid-cols-3 gap-1 sm:grid-cols-4 lg:grid-cols-6">
      {sources.map((source, i) => (
        <SourceItem key={i} source={source} onOpenImage={onOpenImage} />
      ))}
    </ul>
  )
}

function VisualReferenceCard({ visual, onOpenImage }) {
  const { t } = useI18n()
  const title = visual.title || (visual.page ? `${t('eval.page')} ${visual.page}` : t('chat.visualFallbackTitle'))

  return (
    <button
      type="button"
      onClick={() => onOpenImage?.({
        url: visual.image_url,
        title,
        subtitle: visual.subtitle || '',
      })}
      className="group block w-full overflow-hidden rounded-md border border-slate-700 bg-slate-950/40 text-left transition hover:border-sky-500/80 focus:outline-none focus:ring-2 focus:ring-sky-400"
      aria-label={title}
      title={title}
    >
      <div className="aspect-[4/3] bg-slate-950">
        <img
          src={visual.image_url}
          alt={title}
          className="h-full w-full object-contain object-center"
          loading="lazy"
        />
      </div>
      <div className="space-y-1 p-2">
        <p className="truncate text-xs font-semibold text-slate-200">{title}</p>
        {visual.subtitle && (
          <p className="line-clamp-2 text-[11px] text-slate-500">{visual.subtitle}</p>
        )}
      </div>
    </button>
  )
}

function visualTitle(visual, t) {
  return visual.title || (visual.page ? `${t('eval.page')} ${visual.page}` : t('chat.visualFallbackTitle'))
}

function visualTermEntries(visualRefs = []) {
  const seen = new Set()
  return (visualRefs || [])
    .flatMap((visual) => (visual.matched_terms || []).map((term) => ({
      term: String(term || '').trim(),
      visual,
    })))
    .filter(({ term }) => term.length >= 2)
    .filter(({ term }) => {
      const key = term.toLowerCase()
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .sort((a, b) => b.term.length - a.term.length)
}

function splitWithVisualTerms(text, entries, onOpenImage, t) {
  if (!text || entries.length === 0) return text

  const chunks = []
  let cursor = 0
  const lowerText = text.toLowerCase()

  while (cursor < text.length) {
    let best = null
    for (const entry of entries) {
      const lowerTerm = entry.term.toLowerCase()
      const index = lowerText.indexOf(lowerTerm, cursor)
      if (index < 0) continue
      if (
        !best
        || index < best.index
        || (index === best.index && entry.term.length > best.entry.term.length)
      ) {
        best = { index, entry }
      }
    }

    if (!best) {
      chunks.push(text.slice(cursor))
      break
    }

    if (best.index > cursor) {
      chunks.push(text.slice(cursor, best.index))
    }

    const matchedText = text.slice(best.index, best.index + best.entry.term.length)
    chunks.push(
      <VisualTermInline
        key={`${best.entry.visual.image_url}-${best.index}-${matchedText}`}
        text={matchedText}
        visual={best.entry.visual}
        onOpenImage={onOpenImage}
        t={t}
      />,
    )
    cursor = best.index + best.entry.term.length
  }

  return chunks
}

function highlightVisualChildren(children, entries, onOpenImage, t) {
  return React.Children.toArray(children).flatMap((child, index) => {
    if (typeof child === 'string') {
      return splitWithVisualTerms(child, entries, onOpenImage, t)
    }
    if (typeof child === 'number') {
      return splitWithVisualTerms(String(child), entries, onOpenImage, t)
    }
    if (React.isValidElement(child)) {
      const childChildren = child.props?.children
      return React.cloneElement(child, {
        key: child.key || `visual-child-${index}`,
        children: childChildren
          ? highlightVisualChildren(childChildren, entries, onOpenImage, t)
          : childChildren,
      })
    }
    return child
  })
}

function VisualTermInline({ text, visual, onOpenImage, t }) {
  const title = visualTitle(visual, t)
  const subtitle = visual.subtitle || ''
  const openImage = () => onOpenImage?.({ url: visual.image_url, title, subtitle })

  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        onClick={openImage}
        className="inline rounded border-b border-dashed border-sky-300/80 bg-sky-400/10 px-0.5 font-semibold text-sky-100 outline-none transition hover:bg-sky-400/20 focus-visible:ring-2 focus-visible:ring-sky-400"
        title={title}
      >
        {text}
      </button>
      <span className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 w-48 -translate-x-1/2 rounded-md border border-sky-500/50 bg-slate-950 p-2 text-left opacity-0 shadow-2xl shadow-black/50 transition group-hover:opacity-100 group-focus-within:opacity-100">
        <span className="block overflow-hidden rounded border border-slate-700 bg-slate-900">
          <img
            src={visual.image_url}
            alt={title}
            className="h-28 w-full object-contain"
            loading="lazy"
          />
        </span>
        <span className="mt-2 block truncate text-xs font-semibold text-slate-100">{title}</span>
        {subtitle && <span className="mt-0.5 block line-clamp-2 text-[11px] text-slate-500">{subtitle}</span>}
      </span>
    </span>
  )
}

function MarkdownWithVisualTerms({ text, visualRefs, onOpenImage }) {
  const { t } = useI18n()
  const entries = React.useMemo(() => visualTermEntries(visualRefs), [visualRefs])
  const components = React.useMemo(() => {
    const wrap = (Tag, className = '') => function WrappedMarkdownNode({ children, ...props }) {
      return (
        <Tag {...props} className={className || props.className}>
          {highlightVisualChildren(children, entries, onOpenImage, t)}
        </Tag>
      )
    }
    return {
      p: wrap('p'),
      li: wrap('li'),
      strong: wrap('strong'),
      em: wrap('em'),
      h1: wrap('h1'),
      h2: wrap('h2'),
      h3: wrap('h3'),
      h4: wrap('h4'),
      blockquote: wrap('blockquote'),
    }
  }, [entries, onOpenImage, t])

  return <ReactMarkdown components={components}>{text}</ReactMarkdown>
}

function ImageLightbox({ image, onClose }) {
  const { t } = useI18n()
  const [zoom, setZoom] = React.useState(1)
  const [pan, setPan] = React.useState({ x: 0, y: 0 })
  const [dragging, setDragging] = React.useState(false)
  const dragRef = React.useRef({ active: false, startX: 0, startY: 0, originX: 0, originY: 0 })

  React.useEffect(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }, [image?.url])

  const changeZoom = React.useCallback((delta) => {
    setZoom((current) => {
      const next = Math.min(4, Math.max(0.5, Number((current + delta).toFixed(2))))
      if (next <= 1) {
        setPan({ x: 0, y: 0 })
      }
      return next
    })
  }, [])

  const resetView = React.useCallback(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }, [])

  React.useEffect(() => {
    if (!image) return undefined
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
      if (event.key === '+' || event.key === '=') changeZoom(0.25)
      if (event.key === '-' || event.key === '_') changeZoom(-0.25)
      if (event.key === '0') resetView()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [changeZoom, image, onClose, resetView])

  const handlePointerDown = (event) => {
    if (zoom <= 1) return
    event.preventDefault()
    event.currentTarget.setPointerCapture?.(event.pointerId)
    dragRef.current = {
      active: true,
      startX: event.clientX,
      startY: event.clientY,
      originX: pan.x,
      originY: pan.y,
    }
    setDragging(true)
  }

  const handlePointerMove = (event) => {
    if (!dragRef.current.active) return
    event.preventDefault()
    setPan({
      x: dragRef.current.originX + event.clientX - dragRef.current.startX,
      y: dragRef.current.originY + event.clientY - dragRef.current.startY,
    })
  }

  const endDrag = (event) => {
    if (!dragRef.current.active) return
    dragRef.current.active = false
    event.currentTarget.releasePointerCapture?.(event.pointerId)
    setDragging(false)
  }

  if (!image) return null
  const highlightRegions = Array.isArray(image.highlightRegions) ? image.highlightRegions : []

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="relative max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-lg border border-slate-700 bg-slate-900 shadow-2xl shadow-black/50"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-700/80 px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-100">{image.title}</p>
            {image.subtitle && <p className="truncate text-xs text-slate-500">{image.subtitle}</p>}
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              onClick={() => changeZoom(-0.25)}
              className="rounded-md border border-slate-700 p-1.5 text-slate-300 transition hover:border-sky-400 hover:text-white disabled:cursor-not-allowed disabled:opacity-45"
              aria-label="Zoom out"
              title="Zoom out"
              disabled={zoom <= 0.5}
            >
              <ZoomOut size={18} />
            </button>
            <span className="min-w-12 text-center font-mono text-xs text-slate-400">{Math.round(zoom * 100)}%</span>
            <button
              type="button"
              onClick={() => changeZoom(0.25)}
              className="rounded-md border border-slate-700 p-1.5 text-slate-300 transition hover:border-sky-400 hover:text-white disabled:cursor-not-allowed disabled:opacity-45"
              aria-label="Zoom in"
              title="Zoom in"
              disabled={zoom >= 4}
            >
              <ZoomIn size={18} />
            </button>
            <button
              type="button"
              onClick={resetView}
              className="rounded-md border border-slate-700 p-1.5 text-slate-300 transition hover:border-sky-400 hover:text-white"
              aria-label="Reset zoom"
              title="Reset zoom"
            >
              <RotateCcw size={18} />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-slate-700 p-1.5 text-slate-300 transition hover:border-sky-400 hover:text-white"
              aria-label={t('assets.close')}
              title={t('assets.close')}
            >
              <X size={18} />
            </button>
          </div>
        </div>
        <div className="h-[82vh] overflow-hidden bg-slate-950/60 p-4">
          <div className="flex h-full w-full items-center justify-center overflow-hidden">
            <div
              className={`relative inline-block select-none touch-none ${
                zoom > 1 ? (dragging ? 'cursor-grabbing' : 'cursor-grab') : 'cursor-default'
              }`}
              style={{
                transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom})`,
                transformOrigin: 'center center',
              }}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={endDrag}
              onPointerCancel={endDrag}
            >
            <img
              src={image.url}
              alt={image.title}
              className="block max-h-[78vh] max-w-full rounded-md object-contain"
              draggable={false}
            />
            {highlightRegions.map((region, index) => (
              <div
                key={`${region.x}-${region.y}-${region.width}-${region.height}-${index}`}
                className="pointer-events-none absolute rounded-sm border-2 border-amber-300 bg-amber-300/20 shadow-[0_0_0_9999px_rgba(2,6,23,0.14),0_0_24px_rgba(251,191,36,0.75)]"
                style={{
                  left: `${Math.max(0, Math.min(1, Number(region.x) || 0)) * 100}%`,
                  top: `${Math.max(0, Math.min(1, Number(region.y) || 0)) * 100}%`,
                  width: `${Math.max(0, Math.min(1, Number(region.width) || 0)) * 100}%`,
                  height: `${Math.max(0, Math.min(1, Number(region.height) || 0)) * 100}%`,
                }}
              >
                <span className="absolute -left-0.5 -top-6 rounded bg-amber-300 px-1.5 py-0.5 text-[11px] font-semibold text-slate-950 shadow">
                  重点区域
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
    </div>
  )
}

function ResponseTiming({ metrics }) {
  if (!metrics?.total_ms) return null

  const scoreColor = {
    excellent: 'text-emerald-300',
    acceptable: 'text-sky-300',
    slow: 'text-amber-300',
    poor: 'text-red-300',
  }[metrics.score] || 'text-slate-300'

  const search = metrics.search || {}
  const llm = metrics.llm || {}
  const rows = [
    ['total', metrics.total_ms],
    ['retrieval', metrics.retrieval_ms],
    ['query embedding', search.query_embedding_ms],
    ['rerank', search.external_rerank_ms],
    ['LLM', metrics.llm_ms],
    ['first token', llm.ttfb_ms],
    ['stream', llm.stream_duration_ms],
    ['continuation', llm.continuation_ms],
    ['sources', metrics.source_build_ms],
    ['visuals', metrics.visual_refs_ms],
    ['db', metrics.db_ms],
  ].filter(([, value]) => value !== null && value !== undefined && value !== 0)

  return (
    <details className="mt-3 rounded border border-slate-700/70 bg-slate-950/35 p-2 text-xs text-slate-400">
      <summary className="cursor-pointer select-none">
        Response {formatMs(metrics.total_ms)} · <span className={scoreColor}>{metrics.score}</span>
      </summary>
      <div className="mt-2 grid gap-1 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-3 rounded bg-slate-950/50 px-2 py-1">
            <span>{label}</span>
            <span className="font-mono text-slate-300">{formatMs(value)}</span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-slate-500">
        chunks {search.chunks_scanned ?? '-'} · calls {llm.completion_calls ?? '-'} · tokens {llm.total_tokens ?? '-'}
      </p>
    </details>
  )
}

function DetailedAnswer({ message, onOpenImage }) {
  const { t } = useI18n()
  if (!message.detailed_response) return null

  return (
    <details open className="mt-3 rounded-md border border-sky-800/50 bg-slate-950/25 p-3">
      <summary className="cursor-pointer select-none text-xs font-semibold text-sky-200">
        {t('chat.detailedExplanation')}
      </summary>
      <div className="prose prose-sm prose-invert mt-3 max-w-none text-sm">
        <MarkdownWithVisualTerms
          text={message.detailed_response}
          visualRefs={message.detailed_visual_refs}
          onOpenImage={onOpenImage}
        />
      </div>
      {message.detailed_visual_refs && message.detailed_visual_refs.length > 0 && (
        <div className="mt-3 border-t border-slate-700 pt-3 text-xs text-slate-400">
          <p className="mb-2 font-medium text-slate-300">{t('chat.relatedVisuals')}</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {message.detailed_visual_refs.map((visual, i) => (
              <VisualReferenceCard key={`${visual.image_url}-detail-${i}`} visual={visual} onOpenImage={onOpenImage} />
            ))}
          </div>
        </div>
      )}
      {message.detailed_sources && message.detailed_sources.length > 0 && (
        <div className="mt-3 border-t border-slate-700 pt-3 text-xs text-slate-400">
          <p className="mb-2 font-medium text-slate-300">{t('chat.sources')}</p>
          <SourceGrid sources={message.detailed_sources} onOpenImage={onOpenImage} />
        </div>
      )}
      <ResponseTiming metrics={message.detailed_performance_metrics} />
    </details>
  )
}

function formatMs(value) {
  const ms = Number(value || 0)
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

export default function ChatBox({ gameId, gameName }) {
  const { messages, setMessages, loading, setLoading } = useChatStore()
  const { t } = useI18n()
  const safeMessages = Array.isArray(messages) ? messages : []
  const [input, setInput] = React.useState('')
  const [terms, setTerms] = React.useState([])
  const [expandingId, setExpandingId] = React.useState(null)
  const [showBackTop, setShowBackTop] = React.useState(false)
  const [loadingSeconds, setLoadingSeconds] = React.useState(0)
  const [previewImage, setPreviewImage] = React.useState(null)
  const messagesEndRef = React.useRef(null)
  const inputRef = React.useRef(null)

  React.useEffect(() => {
    loadHistory()
    if (SHOW_GLOSSARY_CHIPS) {
      loadGlossary()
    }
  }, [gameId])

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  React.useEffect(() => {
    const handleScroll = () => {
      setShowBackTop(window.scrollY > 520)
    }

    handleScroll()
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  React.useEffect(() => {
    if (!loading) {
      setLoadingSeconds(0)
      return undefined
    }

    const started = Date.now()
    const timer = window.setInterval(() => {
      setLoadingSeconds(Math.max(1, Math.round((Date.now() - started) / 1000)))
    }, 500)
    return () => window.clearInterval(timer)
  }, [loading])

  const loadHistory = async () => {
    try {
      const response = await chatAPI.history(gameId)
      setMessages([...response.data.messages].reverse().map((message) => (
        isBeginnerPrompt(message.user_message)
          ? { ...message, user_message: t('chat.beginnerDisplayMessage', { game: gameName }) }
          : message
      )))
    } catch (error) {
      console.error('Failed to load chat history')
    }
  }

  const loadGlossary = async () => {
    try {
      const response = await glossaryAPI.list(gameId, { enabled_only: true, limit: 18 })
      setTerms(response.data)
    } catch (error) {
      setTerms([])
    }
  }

  const sendMessage = async (message, options = {}) => {
    const userMessage = message.trim()
    if (!userMessage || loading) return
    setInput('')
    setLoading(true)
    const displayUserMessage = options.displayMessage || userMessage
    const requestAnswerMode = options.answerMode || 'concise'
    const tempId = `stream-${Date.now()}`
    let receivedDelta = false
    let finalReceived = false
    setMessages((current) => [
      ...current,
      {
        id: tempId,
        user_message: displayUserMessage,
        assistant_response: '',
        sources: null,
        visual_refs: null,
        performance_metrics: null,
        created_at: new Date().toISOString(),
        streaming: true,
      },
    ])

    try {
      await chatAPI.askStream(gameId, userMessage, {
        displayMessage: options.displayMessage,
        retrievalMessage: options.retrievalMessage,
        answerMode: requestAnswerMode,
        onEvent: ({ event, data }) => {
          if (event === 'delta') {
            receivedDelta = true
            const text = data.text || ''
            setMessages((current) => current.map((msg) => (
              msg.id === tempId
                ? { ...msg, assistant_response: `${msg.assistant_response || ''}${text}` }
                : msg
            )))
          }
          if (event === 'final') {
            finalReceived = true
            setMessages((current) => current.map((msg) => (
              msg.id === tempId
                ? { ...data, created_at: data.created_at || msg.created_at, streaming: false }
                : msg
            )))
          }
          if (event === 'error') {
            throw new Error(data.detail || t('toast.chatFailed'))
          }
        },
      })
      if (!finalReceived) {
        throw new Error(t('toast.chatFailed'))
      }
    } catch (error) {
      if (!receivedDelta) {
        try {
          const response = await chatAPI.ask(gameId, userMessage, {
            displayMessage: options.displayMessage,
            retrievalMessage: options.retrievalMessage,
            answerMode: requestAnswerMode,
          })
          setMessages((current) => current.map((msg) => (
            msg.id === tempId ? response.data : msg
          )))
          return
        } catch (fallbackError) {
          const errorMsg = typeof fallbackError.response?.data?.detail === 'string'
            ? fallbackError.response.data.detail
            : t('toast.chatFailed')
          toast.error(errorMsg)
        }
      } else {
        toast.error(error.message || t('toast.chatFailed'))
      }
      setMessages((current) => current.filter((msg) => msg.id !== tempId))
    } finally {
      setLoading(false)
    }
  }

  const handleSendMessage = async (e) => {
    e.preventDefault()
    await sendMessage(input)
  }

  const insertInputNewline = () => {
    const element = inputRef.current
    if (!element) {
      setInput((current) => `${current}\n`)
      return
    }

    const start = element.selectionStart ?? input.length
    const end = element.selectionEnd ?? input.length
    const nextValue = `${input.slice(0, start)}\n${input.slice(end)}`
    setInput(nextValue)
    window.requestAnimationFrame(() => {
      element.selectionStart = start + 1
      element.selectionEnd = start + 1
    })
  }

  const handleInputKeyDown = (event) => {
    if (event.key !== 'Enter' || event.nativeEvent?.isComposing) {
      return
    }

    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) {
      event.preventDefault()
      insertInputNewline()
      return
    }

    event.preventDefault()
    sendMessage(input)
  }

  const handleTermClick = async (term) => {
    setInput(t('chat.explainTerm', { term: term.term }))
    inputRef.current?.focus()
  }

  const handleBeginnerGuide = async () => {
    const displayMessage = t('chat.beginnerDisplayMessage', { game: gameName })
    await sendMessage(t('chat.beginnerPrompt', { game: gameName }), {
      displayMessage,
      retrievalMessage: displayMessage,
      answerMode: 'detailed',
    })
  }

  const handleExpandMessage = async (id) => {
    if (expandingId) return
    setExpandingId(id)
    try {
      const response = await chatAPI.expand(id)
      setMessages((current) => current.map((msg) => (
        msg.id === id ? response.data : msg
      )))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.expandFailed')
      toast.error(errorMsg)
    } finally {
      setExpandingId(null)
    }
  }

  const handleDeleteMessage = async (id) => {
    try {
      await chatAPI.deleteMessage(id)
      setMessages((current) => (Array.isArray(current) ? current.filter((m) => m.id !== id) : []))
      toast.success(t('toast.messageDeleted'))
    } catch (error) {
      toast.error(t('toast.messageDeleteFailed'))
    }
  }

  return (
    <div className="relative flex flex-col rounded-lg border border-slate-700/80 bg-slate-900/80 shadow-xl shadow-black/25">
      <div className="shrink-0 border-b border-slate-700/80 bg-slate-950/30 p-6">
        <p className="text-xs uppercase tracking-[0.18em] text-sky-300">{t('chat.title')}</p>
        <h2 className="mt-1 text-xl font-bold text-slate-100">{gameName}</h2>
        <p className="text-sm text-slate-500">{t('chat.subtitle')}</p>
      </div>

      <div className="p-6">
        {safeMessages.length === 0 ? (
          <div className="flex min-h-36 items-center justify-center text-center">
            <div>
              <p className="mb-2 text-slate-400">{t('chat.noMessages')}</p>
              <p className="text-sm text-slate-500">{t('chat.startPrompt')}</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {safeMessages.map((msg) => {
              const hasAssistantContent = Boolean((msg.assistant_response || '').trim())
              const hasAssistantDetails = Boolean(
                hasAssistantContent
                || msg.streaming
                || msg.sources?.length
                || msg.visual_refs?.length
                || msg.detailed_response
                || msg.performance_metrics
              )

              return (
              <div key={msg.id} className="space-y-3">
                <div className="flex justify-end">
                  <div className="max-w-xs rounded-md bg-sky-600 px-4 py-2 text-white shadow-lg shadow-sky-950/20 lg:max-w-md">
                    <p className="text-sm">{msg.user_message}</p>
                  </div>
                </div>

                {hasAssistantDetails && (
                <div className="flex justify-start">
                  <div className="max-w-xs rounded-md border border-slate-700 bg-slate-800/90 px-4 py-3 text-slate-100 lg:max-w-2xl">
                    {hasAssistantContent ? (
                      <div className="prose prose-sm prose-invert max-w-none text-sm">
                        <MarkdownWithVisualTerms
                          text={msg.assistant_response}
                          visualRefs={msg.visual_refs}
                          onOpenImage={setPreviewImage}
                        />
                      </div>
                    ) : (
                      msg.streaming && (
                        <div className="flex items-center gap-2 text-sm text-slate-400">
                          <Loader size={16} className="animate-spin text-sky-300" />
                          {t('chat.generating', { seconds: loadingSeconds || 1 })}
                        </div>
                      )
                    )}
                    {msg.sources && msg.sources.length > 0 && (
                      <>
                        {msg.visual_refs && msg.visual_refs.length > 0 && (
                          <div className="mt-3 border-t border-slate-700 pt-3 text-xs text-slate-400">
                            <p className="mb-2 font-medium text-slate-300">{t('chat.relatedVisuals')}</p>
                            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                              {msg.visual_refs.map((visual, i) => (
                                <VisualReferenceCard key={`${visual.image_url}-${i}`} visual={visual} onOpenImage={setPreviewImage} />
                              ))}
                            </div>
                          </div>
                        )}
                      <div className="mt-3 border-t border-slate-700 pt-3 text-xs text-slate-400">
                        <p className="mb-2 font-medium text-slate-300">{t('chat.sources')}</p>
                        <SourceGrid sources={msg.sources} onOpenImage={setPreviewImage} />
                      </div>
                      </>
                    )}
                    <DetailedAnswer message={msg} onOpenImage={setPreviewImage} />
                    <ResponseTiming metrics={msg.performance_metrics} />
                    {!msg.streaming && !msg.detailed_response && (
                      <button
                        type="button"
                        onClick={() => handleExpandMessage(msg.id)}
                        disabled={Boolean(expandingId)}
                        className="mt-2 inline-flex items-center gap-1.5 rounded border border-slate-700 px-2.5 py-1 text-xs text-slate-300 transition hover:border-sky-500 hover:text-sky-100 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {expandingId === msg.id ? <Loader size={14} className="animate-spin" /> : <BookOpenText size={14} />}
                        {expandingId === msg.id ? t('chat.expanding') : t('chat.expandDetailed')}
                      </button>
                    )}
                    <button
                      onClick={() => handleDeleteMessage(msg.id)}
                      className="mt-2 text-slate-500 transition-colors hover:text-red-400"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                )}
              </div>
              )
            })}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSendMessage} className="shrink-0 border-t border-slate-700/80 bg-slate-950/30 p-6">
        <div className="mb-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleBeginnerGuide}
            disabled={loading}
            className="steam-ghost px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-50"
            title={t('chat.beginnerGuideTitle')}
          >
            <Compass size={16} />
            {t('chat.beginnerGuide')}
          </button>
        </div>
        {SHOW_GLOSSARY_CHIPS && terms.length > 0 && (
          <div className="mb-3">
            <div className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
              {t('chat.glossary')}
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {terms.map((term) => (
                <button
                  key={term.id}
                  type="button"
                  onClick={() => handleTermClick(term)}
                  disabled={loading}
                  title={term.description || term.aliases?.join(', ')}
                  className="glossary-chip shrink-0 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {term.term}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder={t('chat.placeholder')}
            disabled={loading}
            rows={1}
            className="input min-h-[44px] flex-1 resize-y py-2"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="btn-primary p-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? <Loader size={20} className="animate-spin" /> : <Send size={20} />}
          </button>
        </div>
        {loading && (
          <p className="mt-2 text-xs text-slate-500">
            {t('chat.generating', { seconds: loadingSeconds || 1 })}
          </p>
        )}
      </form>

      {showBackTop && (
        <button
          type="button"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="fixed bottom-6 right-6 z-40 rounded-full border border-slate-600/80 bg-slate-900/95 p-3 text-sky-200 shadow-xl shadow-black/35 transition hover:border-sky-400 hover:bg-slate-800 hover:text-white"
          aria-label={t('chat.backTop')}
          title={t('chat.backTop')}
        >
          <ArrowUp size={20} />
        </button>
      )}
      <ImageLightbox image={previewImage} onClose={() => setPreviewImage(null)} />
    </div>
  )
}
