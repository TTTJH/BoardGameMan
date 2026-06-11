import React from 'react'
import { AlertTriangle, Crop, FileQuestion, FileText, GitMerge, Loader, Scissors, Trash2, Upload } from 'lucide-react'
import { useDocumentStore, useGameStore } from '../store'
import { documentsAPI, evalsAPI, gamesAPI, glossaryAPI } from '../api/client'
import toast from 'react-hot-toast'
import { useI18n } from '../i18n'

const RULE_TYPES = [
  'setup',
  'turn_structure',
  'action',
  'scoring',
  'end_game',
  'variant',
  'example',
  'component',
  'text',
]

const SHOW_GLOSSARY_PANEL = false
const RULE_SCOPES = ['base', 'variant', 'example']
const DOCUMENT_SOURCE_TYPES = [
  'official_rulebook',
  'official_walkthrough',
  'official_faq',
  'official_errata',
  'official_tutorial',
  'community_qa',
  'player_guide',
  'house_rule',
]
const FAILURE_TYPES = [
  'unreviewed',
  'bad_eval_case',
  'pdf_parse_noise',
  'chunk_boundary',
  'retrieval_miss',
  'term_too_strict',
  'variant_noise',
  'accepted',
]

function ProcessingReportSummary({ report, documentId, onOpenLayout }) {
  const { t } = useI18n()

  if (!report) {
    return (
      <div className="mt-3 rounded border border-slate-700 bg-slate-950/30 p-3 text-xs text-slate-500">
        {t('report.none')}
      </div>
    )
  }

  const ruleTypes = Object.entries(report.rule_type_counts || {})
    .sort((left, right) => right[1] - left[1])
    .slice(0, 5)
  const ruleScopes = Object.entries(report.rule_scope_counts || {})
    .sort((left, right) => right[1] - left[1])
  const lowQualityIssues = report.low_quality_chunks || report.low_quality_chunk_details || []

  return (
    <div className="mt-3 space-y-3 rounded border border-slate-700 bg-slate-950/30 p-3 text-xs text-slate-400">
      <div className="grid grid-cols-2 gap-2">
        <ReportMetric label={t('report.pages')} value={report.page_count} />
        <ReportMetric label={t('report.chunks')} value={report.chunk_count} />
        <ReportMetric label={t('report.lowQuality')} value={report.low_quality_chunk_count} />
        <ReportMetric label={t('report.emptyPages')} value={(report.empty_text_pages || []).length} />
        <ReportMetric label={t('report.suspiciousPages')} value={(report.suspicious_pages || []).length} />
        <ReportMetric
          label={t('report.embedding')}
          value={report.embedding?.success ? t('report.ready') : report.embedding?.attempted ? t('report.failed') : t('report.skipped')}
        />
      </div>
      {ruleTypes.length > 0 && (
        <div>
          <p className="mb-1 font-medium text-slate-300">{t('report.ruleUnits')}</p>
          <div className="flex flex-wrap gap-1">
            {ruleTypes.map(([type, count]) => (
              <span key={type} className="rounded border border-slate-700 bg-slate-900 px-2 py-1">
                {type}: {count}
              </span>
            ))}
          </div>
        </div>
      )}
      {ruleScopes.length > 0 && (
        <div>
          <p className="mb-1 font-medium text-slate-300">{t('report.ruleScope')}</p>
          <div className="flex flex-wrap gap-1">
            {ruleScopes.map(([scope, count]) => (
              <span key={scope} className="rounded border border-slate-700 bg-slate-900 px-2 py-1">
                {scope}: {count}
              </span>
            ))}
          </div>
        </div>
      )}
      {report.suspicious_pages?.length > 0 && (
        <div>
          <p className="mb-1 font-medium text-amber-300">{t('report.needsReview')}</p>
          <p>
            {t('report.pagesList', { pages: report.suspicious_pages.map((page) => page.page).join(', ') })}
          </p>
        </div>
      )}
      {lowQualityIssues.length > 0 && (
        <div className="rounded border border-amber-500/30 bg-amber-500/10 p-2">
          <p className="mb-2 flex items-center gap-1 font-medium text-amber-200">
            <AlertTriangle size={14} />
            {t('report.lowQualityDetails')}
          </p>
          <div className="space-y-2">
            {lowQualityIssues.slice(0, 4).map((issue, index) => (
              <div key={`${issue.page}-${issue.section || issue.type}-${index}`} className="rounded border border-amber-500/20 bg-slate-950/50 p-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold text-slate-200">
                    {t('eval.page')} {issue.page || '-'} · {issue.section || issue.type || '-'}
                  </p>
                  {issue.page && onOpenLayout && (
                    <button
                      type="button"
                      onClick={() => onOpenLayout({ documentId, page: Number(issue.page) })}
                      className="steam-ghost px-2 py-1 text-[11px]"
                    >
                      <Crop size={13} />
                      {t('report.openLayout')}
                    </button>
                  )}
                </div>
                {issue.reasons?.length > 0 && (
                  <p className="mt-1 text-amber-100/80">
                    {issue.reasons.map((reason) => formatLowQualityReason(reason, t)).join(' · ')}
                  </p>
                )}
                {issue.preview && (
                  <p className="mt-1 line-clamp-2 break-words text-slate-500">{issue.preview}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {lowQualityIssues.length === 0 && Number(report.low_quality_chunk_count || 0) > 0 && (
        <p className="rounded border border-amber-500/30 bg-amber-500/10 p-2 text-amber-200">
          {t('report.lowQualityFallback')}
        </p>
      )}
      <p className="text-slate-500">{report.eval?.summary}</p>
    </div>
  )
}

function formatLowQualityReason(reason, t) {
  const [code, value = ''] = String(reason).split(':')
  return t(`report.reason.${code}`, { value })
}

function ReportMetric({ label, value }) {
  return (
    <div className="rounded bg-slate-900/80 px-2 py-1">
      <span className="text-slate-500">{label}</span>
      <div className="font-semibold text-slate-200">{value ?? '-'}</div>
    </div>
  )
}

function FailureAnalysisPanel({ analysis }) {
  const { t } = useI18n()

  if (!analysis?.available) return null

  return (
    <div className="mt-3 rounded border border-slate-700 bg-slate-950/40 p-3 text-xs text-slate-400">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-200">{t('analysis.title')}</p>
          <p className="text-slate-500">
            {t('analysis.failedCases', { failed: analysis.failed_count, count: analysis.case_count })}
          </p>
        </div>
        <span className="rounded border border-slate-700 bg-slate-900 px-2 py-1">
          run #{analysis.run_id}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <AnalysisList title={t('analysis.suggestedTypes')} items={objectEntries(analysis.suggested_failure_counts)} />
        <AnalysisList title={t('analysis.missingTerms')} items={analysis.frequent_missing_terms} />
        <AnalysisList title={t('analysis.missedPages')} items={analysis.missed_expected_pages} />
        <AnalysisList title={t('analysis.topWrongSections')} items={analysis.frequent_top_sections} />
      </div>

      {analysis.actions?.length > 0 && (
        <div className="mt-3 rounded border border-slate-700 bg-slate-900/60 p-2">
          <p className="mb-1 font-semibold text-slate-300">{t('analysis.suggestedActions')}</p>
          {analysis.actions.map((action) => (
            <p key={action} className="text-slate-400">{action}</p>
          ))}
        </div>
      )}
    </div>
  )
}

function AnalysisList({ title, items }) {
  const { t } = useI18n()
  const visibleItems = (items || []).slice(0, 5)
  return (
    <div className="rounded border border-slate-700 bg-slate-900/60 p-2">
      <p className="mb-1 font-semibold text-slate-300">{title}</p>
      {visibleItems.length === 0 ? (
        <p className="text-slate-500">{t('analysis.none')}</p>
      ) : (
        <div className="space-y-1">
          {visibleItems.map((item) => (
            <p key={`${title}-${item.value}`} className="flex justify-between gap-3">
              <span className="min-w-0 truncate">{item.value}</span>
              <span className="text-slate-500">{item.count}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

function objectEntries(value = {}) {
  return Object.entries(value).map(([entryValue, count]) => ({ value: entryValue, count }))
}

function EvalRunDetails({ evalResult, onUpdateCase }) {
  const { t } = useI18n()
  const [open, setOpen] = React.useState(false)
  const [edits, setEdits] = React.useState({})

  if (!evalResult?.results?.length) {
    return null
  }

  const failures = evalResult.results.filter((result) => !result.passed)
  const visibleResults = open ? evalResult.results : failures.slice(0, 6)
  const editValue = (result, key, fallback) => edits[result.case_id]?.[key] ?? fallback
  const updateEdit = (caseId, patch) => {
    setEdits((current) => ({
      ...current,
      [caseId]: {
        ...(current[caseId] || {}),
        ...patch,
      },
    }))
  }

  return (
    <div className="mt-3 rounded border border-slate-700 bg-slate-950/30 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-200">{t('eval.details')}</p>
          <p className="text-xs text-slate-500">
            {t('analysis.failedCases', { failed: failures.length, count: evalResult.results.length })}
          </p>
        </div>
        <button type="button" onClick={() => setOpen(!open)} className="steam-ghost px-3 py-1 text-xs">
          {open ? t('eval.showFailed') : t('eval.showAll')}
        </button>
      </div>

      <div className="mt-3 max-h-96 space-y-3 overflow-y-auto pr-1">
        {visibleResults.map((result) => (
          <div
            key={result.case_id}
            className={`rounded border p-3 text-xs ${
              result.passed
                ? 'border-emerald-900/70 bg-emerald-950/20'
                : 'border-slate-700 bg-slate-900/70'
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-slate-100">
                  {result.passed ? 'PASS' : 'FAIL'} · {result.question}
                </p>
                <p className="mt-1 text-slate-500">
                  {t('eval.expected')} {JSON.stringify(result.expected_pages)} · {t('eval.found')} {JSON.stringify(result.found_pages)} · {t('eval.terms')} {Math.round(result.term_coverage * 100)}%
                  {result.answer_term_coverage !== null && result.answer_term_coverage !== undefined && (
                    <> · {t('eval.answer')} {Math.round(result.answer_term_coverage * 100)}%</>
                  )}
                  {result.cited_source_hit !== null && result.cited_source_hit !== undefined && (
                    <> · {t('eval.source')} {result.cited_source_hit ? t('eval.hit') : t('eval.miss')}</>
                  )}
                </p>
              </div>
              <label className="inline-flex items-center gap-1 text-slate-400">
                <input
                  type="checkbox"
                  checked={result.enabled}
                  onChange={(event) => onUpdateCase(result.case_id, { enabled: event.target.checked })}
                />
                {t('eval.enabled')}
              </label>
            </div>

            <div className="mt-2 flex flex-wrap gap-2">
              <select
                value={result.failure_type || 'unreviewed'}
                onChange={(event) => onUpdateCase(result.case_id, { failure_type: event.target.value })}
                className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200"
              >
                {FAILURE_TYPES.map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
              {result.missing_terms?.length > 0 && (
                <span className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-400">
                  {t('eval.missing')}: {result.missing_terms.slice(0, 3).join(', ')}
                </span>
              )}
              {result.suggested_failure_type && result.suggested_failure_type !== result.failure_type && (
                <button
                  type="button"
                  onClick={() => onUpdateCase(result.case_id, { failure_type: result.suggested_failure_type })}
                  className="rounded border border-amber-700/70 bg-amber-950/40 px-2 py-1 text-amber-200"
                >
                  {t('eval.suggest')}: {result.suggested_failure_type}
                </button>
              )}
              <button
                type="button"
                onClick={() => onUpdateCase(result.case_id, { failure_type: 'accepted', enabled: true })}
                className="rounded border border-emerald-700/70 bg-emerald-950/40 px-2 py-1 text-emerald-200"
              >
                {t('eval.accept')}
              </button>
            </div>

            <div className="mt-2 grid gap-2 md:grid-cols-2">
              <input
                value={editValue(result, 'pages', (result.expected_pages || []).join(', '))}
                onChange={(event) => updateEdit(result.case_id, { pages: event.target.value })}
                placeholder={t('eval.pagesPlaceholder')}
                className="input px-2 py-1 text-xs"
              />
              <input
                value={editValue(result, 'terms', (result.expected_terms || []).join(', '))}
                onChange={(event) => updateEdit(result.case_id, { terms: event.target.value })}
                placeholder={t('eval.termsPlaceholder')}
                className="input px-2 py-1 text-xs"
              />
              <input
                value={editValue(result, 'notes', result.review_notes || '')}
                onChange={(event) => updateEdit(result.case_id, { notes: event.target.value })}
                placeholder={t('eval.notesPlaceholder')}
                className="input px-2 py-1 text-xs md:col-span-2"
              />
              <button
                type="button"
                onClick={() => onUpdateCase(result.case_id, {
                  expected_pages: splitNumberList(editValue(result, 'pages', (result.expected_pages || []).join(', '))),
                  expected_terms: splitList(editValue(result, 'terms', (result.expected_terms || []).join(', '))),
                  review_notes: editValue(result, 'notes', result.review_notes || ''),
                })}
                className="steam-ghost px-3 py-1 text-xs md:col-span-2"
              >
                {t('eval.saveReview')}
              </button>
            </div>

            {result.assistant_answer && (
              <div className="mt-2 rounded border border-slate-700 bg-slate-950/50 p-2 text-slate-300">
                <p className="mb-1 font-semibold text-slate-200">{t('eval.assistantAnswer')}</p>
                <p className="line-clamp-6 whitespace-pre-wrap">{result.assistant_answer}</p>
              </div>
            )}

            {result.top_sources?.length > 0 && (
              <div className="mt-2 space-y-1">
                {result.top_sources.slice(0, 2).map((source, index) => (
                  <p key={index} className="line-clamp-2 rounded bg-slate-950/60 p-2 text-slate-400">
                    {t('eval.page')} {source.page || '-'} · {source.excerpt}
                  </p>
                ))}
              </div>
            )}

            {result.diagnostics?.top_results?.length > 0 && (
              <details className="mt-2 rounded border border-slate-700 bg-slate-950/40 p-2 text-slate-400">
                <summary className="cursor-pointer font-semibold text-slate-300">{t('eval.queryDiagnostics')}</summary>
                <p className="mt-2 break-words text-slate-500">
                  {t('eval.expanded')}: {result.diagnostics.expanded_query}
                </p>
                {result.diagnostics.document_intent && (
                  <p className="mt-1 text-slate-500">intent: {result.diagnostics.document_intent}</p>
                )}
                <div className="mt-2 space-y-1">
                  {result.diagnostics.top_results.slice(0, 5).map((item) => (
                    <p key={`${result.case_id}-${item.rank}`} className="rounded bg-slate-950/70 p-2">
                      #{item.rank} {t('eval.score')} {item.score} · {t('eval.page')} {item.page || '-'} · {item.source_type ? t(`sourceType.${item.source_type}`) : '-'} · {item.rule_scope || '-'} / {item.rule_type || '-'} / {item.source_kind || '-'}
                      <br />
                      <span className="text-slate-500">{item.section || item.excerpt}</span>
                    </p>
                  ))}
                </div>
              </details>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function ChunkInspector({ documentId, onChanged }) {
  const { t } = useI18n()
  const [open, setOpen] = React.useState(false)
  const [chunks, setChunks] = React.useState([])
  const [loading, setLoading] = React.useState(false)
  const [savingId, setSavingId] = React.useState(null)
  const [splitPositions, setSplitPositions] = React.useState({})

  const loadChunks = async () => {
    setLoading(true)
    try {
      const response = await documentsAPI.listChunks(documentId)
      setChunks(response.data)
    } catch (error) {
      toast.error(t('toast.chunksLoadFailed'))
    } finally {
      setLoading(false)
    }
  }

  const toggleOpen = async () => {
    const nextOpen = !open
    setOpen(nextOpen)
    if (nextOpen && chunks.length === 0) {
      await loadChunks()
    }
  }

  const updateLocalChunk = (chunkId, patch) => {
    setChunks((current) => current.map((chunk) => (
      chunk.id === chunkId ? { ...chunk, ...patch } : chunk
    )))
  }

  const saveChunk = async (chunk) => {
    setSavingId(`save-${chunk.id}`)
    try {
      const response = await documentsAPI.updateChunk(chunk.id, {
        content: chunk.content,
        rule_type: chunk.rule_type,
        enabled: chunk.enabled,
        keywords: chunk.keywords || '',
        section_title: chunk.section_title || '',
        rule_scope: chunk.rule_scope || 'base',
      })
      updateLocalChunk(chunk.id, response.data)
      await onChanged?.()
      toast.success(t('toast.chunkSaved'))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.chunkSaveFailed')
      toast.error(errorMsg)
    } finally {
      setSavingId(null)
    }
  }

  const splitChunk = async (chunk) => {
    const splitAt = splitPositions[chunk.id] || Math.floor(chunk.content.length / 2)
    if (splitAt <= 0 || splitAt >= chunk.content.length) {
      toast.error(t('toast.splitCursor'))
      return
    }

    setSavingId(`split-${chunk.id}`)
    try {
      const response = await documentsAPI.splitChunk(chunk.id, splitAt)
      setChunks(response.data)
      setSplitPositions({})
      await onChanged?.()
      toast.success(t('toast.chunkSplit'))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.chunkSplitFailed')
      toast.error(errorMsg)
    } finally {
      setSavingId(null)
    }
  }

  const mergeNext = async (chunk) => {
    setSavingId(`merge-${chunk.id}`)
    try {
      const response = await documentsAPI.mergeChunkNext(chunk.id)
      setChunks(response.data)
      setSplitPositions({})
      await onChanged?.()
      toast.success(t('toast.chunksMerged'))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.chunkMergeFailed')
      toast.error(errorMsg)
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="mt-3 rounded border border-slate-700 bg-slate-950/30 p-3">
      <button type="button" onClick={toggleOpen} className="steam-ghost px-3 py-1 text-xs">
        {t('chunks.inspect')}
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader size={16} className="animate-spin" />
              {t('chunks.loading')}
            </div>
          ) : (
            chunks.map((chunk) => (
              <div key={chunk.id} className="rounded border border-slate-700 bg-slate-900/70 p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded bg-slate-950 px-2 py-1 text-slate-400">
                    #{chunk.chunk_index}
                  </span>
                  <select
                    value={chunk.rule_type}
                    onChange={(event) => updateLocalChunk(chunk.id, { rule_type: event.target.value })}
                    className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200"
                  >
                    {RULE_TYPES.map((type) => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                  <select
                    value={chunk.rule_scope || 'base'}
                    onChange={(event) => updateLocalChunk(chunk.id, { rule_scope: event.target.value })}
                    className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200"
                  >
                    {RULE_SCOPES.map((scope) => (
                      <option key={scope} value={scope}>{scope}</option>
                    ))}
                  </select>
                  <label className="inline-flex items-center gap-1 text-slate-400">
                    <input
                      type="checkbox"
                      checked={chunk.enabled}
                      onChange={(event) => updateLocalChunk(chunk.id, { enabled: event.target.checked })}
                    />
                    {t('eval.enabled')}
                  </label>
                  <button
                    type="button"
                    onClick={() => saveChunk(chunk)}
                    disabled={savingId === `save-${chunk.id}`}
                    className="steam-action px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {savingId === `save-${chunk.id}` ? <Loader size={14} className="animate-spin" /> : null}
                    {t('chunks.save')}
                  </button>
                  <button
                    type="button"
                    onClick={() => splitChunk(chunk)}
                    disabled={savingId === `split-${chunk.id}` || chunk.content.length < 2}
                    className="steam-ghost px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {savingId === `split-${chunk.id}` ? (
                      <Loader size={14} className="animate-spin" />
                    ) : (
                      <Scissors size={14} />
                    )}
                    {t('chunks.split')}
                  </button>
                  <button
                    type="button"
                    onClick={() => mergeNext(chunk)}
                    disabled={savingId === `merge-${chunk.id}`}
                    className="steam-ghost px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {savingId === `merge-${chunk.id}` ? (
                      <Loader size={14} className="animate-spin" />
                    ) : (
                      <GitMerge size={14} />
                    )}
                    {t('chunks.mergeNext')}
                  </button>
                </div>
                <input
                  value={chunk.section_title || ''}
                  onChange={(event) => updateLocalChunk(chunk.id, { section_title: event.target.value })}
                  placeholder={t('chunks.sectionTitle')}
                  className="input mb-2 px-3 py-1 text-xs"
                />
                <input
                  value={chunk.keywords || ''}
                  onChange={(event) => updateLocalChunk(chunk.id, { keywords: event.target.value })}
                  placeholder={t('chunks.manualKeywords')}
                  className="input mb-2 px-3 py-1 text-xs"
                />
                <textarea
                  value={chunk.content}
                  onChange={(event) => updateLocalChunk(chunk.id, { content: event.target.value })}
                  onSelect={(event) => {
                    setSplitPositions((current) => ({
                      ...current,
                      [chunk.id]: event.target.selectionStart,
                    }))
                  }}
                  className="input min-h-32 resize-y px-3 py-2 text-xs"
                />
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

function GlossaryPanel({ gameId }) {
  const { t } = useI18n()
  const [terms, setTerms] = React.useState([])
  const [loading, setLoading] = React.useState(false)
  const [savingId, setSavingId] = React.useState(null)

  React.useEffect(() => {
    loadTerms()
  }, [gameId])

  const loadTerms = async () => {
    setLoading(true)
    try {
      const response = await glossaryAPI.list(gameId, { enabled_only: false, limit: 80 })
      setTerms(response.data)
    } catch (error) {
      toast.error('Failed to load glossary')
    } finally {
      setLoading(false)
    }
  }

  const regenerate = async () => {
    setLoading(true)
    try {
      const response = await glossaryAPI.regenerate(gameId)
      setTerms(response.data)
      toast.success(`Generated ${response.data.length} glossary terms`)
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : 'Failed to regenerate glossary'
      toast.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const updateLocalTerm = (termId, patch) => {
    setTerms((current) => current.map((term) => (
      term.id === termId ? { ...term, ...patch } : term
    )))
  }

  const saveTerm = async (term) => {
    setSavingId(term.id)
    try {
      const response = await glossaryAPI.updateTerm(term.id, {
        term: term.term,
        aliases: splitList(term.aliasesText ?? term.aliases?.join(', ')),
        term_type: term.term_type || 'term',
        description: term.description || '',
        related_terms: splitList(term.relatedText ?? term.related_terms?.join(', ')),
        search_terms: splitList(term.searchText ?? term.search_terms?.join(', ')),
        enabled: term.enabled,
      })
      updateLocalTerm(term.id, response.data)
      toast.success('Glossary term saved')
    } catch (error) {
      toast.error('Failed to save glossary term')
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="font-semibold text-slate-100">Glossary</h4>
          <p className="mt-1 text-sm text-slate-500">
            Review terminology used for query rewriting and chat shortcuts.
          </p>
        </div>
        <button
          type="button"
          onClick={regenerate}
          disabled={loading}
          className="steam-ghost shrink-0 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? <Loader size={18} className="animate-spin" /> : <FileQuestion size={18} />}
          Regenerate
        </button>
      </div>

      {loading && terms.length === 0 ? (
        <div className="mt-3 flex items-center gap-2 text-sm text-slate-400">
          <Loader size={16} className="animate-spin" />
          Loading glossary...
        </div>
      ) : (
        <div className="mt-3 max-h-96 space-y-2 overflow-y-auto pr-1">
          {terms.length === 0 ? (
            <p className="rounded border border-slate-700 bg-slate-950/30 p-3 text-sm text-slate-500">
              No glossary terms yet. Regenerate after processing a rulebook.
            </p>
          ) : terms.map((term) => (
            <div key={term.id} className="rounded border border-slate-700 bg-slate-950/30 p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <input
                  value={term.term}
                  onChange={(event) => updateLocalTerm(term.id, { term: event.target.value })}
                  className="input max-w-xs px-3 py-1 text-xs"
                />
                <select
                  value={term.term_type}
                  onChange={(event) => updateLocalTerm(term.id, { term_type: event.target.value })}
                  className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
                >
                  {RULE_TYPES.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                  <option value="term">term</option>
                </select>
                <label className="inline-flex items-center gap-1 text-xs text-slate-400">
                  <input
                    type="checkbox"
                    checked={term.enabled}
                    onChange={(event) => updateLocalTerm(term.id, { enabled: event.target.checked })}
                  />
                  {t('eval.enabled')}
                </label>
                <button
                  type="button"
                  onClick={() => saveTerm(term)}
                  disabled={savingId === term.id}
                  className="steam-action px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {savingId === term.id ? <Loader size={14} className="animate-spin" /> : null}
                  Save
                </button>
              </div>
              <input
                value={term.aliasesText ?? term.aliases?.join(', ') ?? ''}
                onChange={(event) => updateLocalTerm(term.id, { aliasesText: event.target.value })}
                placeholder="Aliases, comma separated"
                className="input mb-2 px-3 py-1 text-xs"
              />
              <textarea
                value={term.description || ''}
                onChange={(event) => updateLocalTerm(term.id, { description: event.target.value })}
                placeholder="Description"
                className="input min-h-16 resize-y px-3 py-2 text-xs"
              />
              <p className="mt-2 text-xs text-slate-500">
                Pages {(term.source_pages || []).join(', ') || '-'} · chunks {(term.chunk_refs || []).slice(0, 6).join(', ') || '-'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function splitList(value = '') {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function splitNumberList(value = '') {
  return splitList(value)
    .map((item) => Number.parseInt(item, 10))
    .filter((item) => Number.isFinite(item))
}

export default function DocumentUpload({ gameId, onOpenLayout }) {
  const { documents, setDocuments, uploading, setUploading, removeDocument } = useDocumentStore()
  const { updateGame } = useGameStore()
  const { t } = useI18n()
  const fileInputRef = React.useRef(null)
  const [generatingCandidates, setGeneratingCandidates] = React.useState(false)
  const [promotingCandidates, setPromotingCandidates] = React.useState(false)
  const [runningEval, setRunningEval] = React.useState(false)
  const [runningChatEval, setRunningChatEval] = React.useState(false)
  const [candidateResult, setCandidateResult] = React.useState(null)
  const [evalResult, setEvalResult] = React.useState(null)
  const [failureAnalysis, setFailureAnalysis] = React.useState(null)
  const [rebuildingReportId, setRebuildingReportId] = React.useState(null)
  const [reprocessingId, setReprocessingId] = React.useState(null)

  React.useEffect(() => {
    loadDocuments()
    loadLatestEval()
    loadFailureAnalysis()
  }, [gameId])

  const loadDocuments = async () => {
    try {
      const response = await documentsAPI.list(gameId)
      setDocuments(response.data)
    } catch (error) {
      toast.error(t('toast.docsLoadFailed'))
    }
  }

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith('.pdf')) {
      toast.error(t('toast.docsOnlyPdf'))
      return
    }

    setUploading(true)
    try {
      const response = await documentsAPI.upload(gameId, file)
      setDocuments([response.data, ...documents])
      try {
        const gameResponse = await gamesAPI.get(gameId)
        updateGame(gameResponse.data)
      } catch (refreshError) {
        toast.error(t('toast.coverRefreshFailed'))
      }
      toast.success(t('toast.docUploaded'))
      fileInputRef.current.value = ''
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.docUploadFailed')
      toast.error(errorMsg)
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteDocument = async (id) => {
    if (!window.confirm(t('docs.deleteConfirm'))) return

    try {
      await documentsAPI.delete(id)
      removeDocument(id)
      toast.success(t('toast.docDeleted'))
    } catch (error) {
      toast.error(t('toast.docDeleteFailed'))
    }
  }

  const handleUpdateDocumentSourceType = async (docId, sourceType) => {
    try {
      const response = await documentsAPI.update(docId, { source_type: sourceType })
      setDocuments(documents.map((doc) => (doc.id === docId ? response.data : doc)))
      toast.success(t('toast.docSourceUpdated'))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.docSourceUpdateFailed')
      toast.error(errorMsg)
    }
  }

  const handleGenerateCandidates = async () => {
    setGeneratingCandidates(true)
    setCandidateResult(null)
    try {
      const response = await evalsAPI.generateCandidates(gameId, {
        max_pages: 4,
        questions_per_page: 2,
      })
      setCandidateResult(response.data)
      toast.success(t('toast.candidatesGenerated', { count: response.data.candidate_count }))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.candidatesFailed')
      toast.error(errorMsg)
    } finally {
      setGeneratingCandidates(false)
    }
  }

  const loadLatestEval = async () => {
    try {
      const response = await evalsAPI.latestRun(gameId)
      setEvalResult(response.data.available === false ? null : response.data)
    } catch (error) {
      setEvalResult(null)
    }
  }

  const loadFailureAnalysis = async (mode = 'retrieval') => {
    try {
      const response = await evalsAPI.failureAnalysis(gameId, { mode })
      setFailureAnalysis(response.data.available === false ? null : response.data)
    } catch (error) {
      setFailureAnalysis(null)
    }
  }

  const handlePromoteCandidates = async () => {
    setPromotingCandidates(true)
    try {
      const response = await evalsAPI.promoteCandidates(gameId)
      toast.success(t('toast.stableEval', { count: response.data.total }))
      setCandidateResult((current) => ({
        ...(current || {}),
        promoted: response.data,
      }))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.promoteFailed')
      toast.error(errorMsg)
    } finally {
      setPromotingCandidates(false)
    }
  }

  const handleRunEval = async () => {
    setRunningEval(true)
    try {
      const response = await evalsAPI.run(gameId, { top_k: 8 })
      setEvalResult(response.data)
      await loadDocuments()
      await loadFailureAnalysis('retrieval')
      toast.success(t('toast.evalPassRate', { rate: Math.round(response.data.pass_rate * 100) }))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.evalFailed')
      toast.error(errorMsg)
    } finally {
      setRunningEval(false)
    }
  }

  const handleRunChatEval = async () => {
    setRunningChatEval(true)
    try {
      const response = await evalsAPI.runChat(gameId, { top_k: 8, max_cases: 10 })
      setEvalResult(response.data)
      await loadDocuments()
      await loadFailureAnalysis('chat')
      toast.success(t('toast.chatEvalPassRate', { rate: Math.round(response.data.pass_rate * 100) }))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.chatEvalFailed')
      toast.error(errorMsg)
    } finally {
      setRunningChatEval(false)
    }
  }

  const handleUpdateEvalCase = async (caseId, patch) => {
    try {
      const response = await evalsAPI.updateCase(caseId, patch)
      setEvalResult((current) => {
        if (!current?.results) return current
        return {
          ...current,
          results: current.results.map((result) => (
            result.case_id === caseId
              ? {
                  ...result,
                  enabled: response.data.enabled,
                  failure_type: response.data.failure_type,
                  review_notes: response.data.review_notes,
                  expected_pages: response.data.expected_pages,
                  expected_terms: response.data.expected_terms,
                }
              : result
          )),
        }
      })
      toast.success(t('toast.evalCaseUpdated'))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.evalCaseUpdateFailed')
      toast.error(errorMsg)
    }
  }

  const handleRebuildReport = async (docId) => {
    setRebuildingReportId(docId)
    try {
      await documentsAPI.rebuildReport(docId)
      await loadDocuments()
      toast.success(t('toast.reportRebuilt'))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.reportFailed')
      toast.error(errorMsg)
    } finally {
      setRebuildingReportId(null)
    }
  }

  const handleReprocess = async (docId) => {
    if (!window.confirm(t('docs.reprocessConfirm'))) {
      return
    }

    setReprocessingId(docId)
    try {
      await documentsAPI.reprocess(docId)
      await loadDocuments()
      toast.success(t('toast.reprocessed'))
    } catch (error) {
      const errorMsg = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.reprocessFailed')
      toast.error(errorMsg)
    } finally {
      setReprocessingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-slate-100">{t('docs.title')}</h3>

      <div className="card p-6">
        <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-600 bg-slate-950/30 p-8 transition-colors hover:border-sky-400 hover:bg-sky-500/5">
          <Upload size={32} className="mb-2 text-sky-300" />
          <span className="text-sm font-medium text-slate-200">
            {uploading ? t('docs.uploading') : t('docs.upload')}
          </span>
          <span className="mt-1 text-xs text-slate-500">{t('docs.maxSize')}</span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileSelect}
            disabled={uploading}
            className="hidden"
          />
        </label>
      </div>

      <div className="card p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h4 className="font-semibold text-slate-100">{t('docs.evalTitle')}</h4>
            <p className="mt-1 text-sm text-slate-500">
              {t('docs.evalDesc')}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={handleGenerateCandidates}
              disabled={generatingCandidates || documents.length === 0}
              className="steam-ghost shrink-0 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {generatingCandidates ? <Loader size={18} className="animate-spin" /> : <FileQuestion size={18} />}
              {t('docs.generate')}
            </button>
            <button
              type="button"
              onClick={handlePromoteCandidates}
              disabled={promotingCandidates || documents.length === 0}
              className="steam-ghost shrink-0 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {promotingCandidates ? <Loader size={18} className="animate-spin" /> : null}
              {t('docs.promote')}
            </button>
            <button
              type="button"
              onClick={handleRunEval}
              disabled={runningEval || runningChatEval || documents.length === 0}
              className="steam-action shrink-0 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {runningEval ? <Loader size={18} className="animate-spin" /> : null}
              {t('docs.runEval')}
            </button>
            <button
              type="button"
              onClick={handleRunChatEval}
              disabled={runningChatEval || runningEval || documents.length === 0}
              className="steam-action shrink-0 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {runningChatEval ? <Loader size={18} className="animate-spin" /> : null}
              {t('docs.runChatEval')}
            </button>
          </div>
        </div>
        {candidateResult && (
          <div className="mt-3 rounded border border-slate-700 bg-slate-950/40 p-3 text-xs text-slate-400">
            <p className="font-medium text-slate-300">
              {t('docs.candidatesWritten', { count: candidateResult.candidate_count })}
            </p>
            <p className="mt-1 break-all">{candidateResult.output_path}</p>
            {candidateResult.promoted && (
              <p className="mt-1">
                {t('docs.promoted', { inserted: candidateResult.promoted.inserted, updated: candidateResult.promoted.updated })}
              </p>
            )}
          </div>
        )}
        {evalResult && (
          <>
            <div className="mt-3 grid grid-cols-2 gap-2 rounded border border-slate-700 bg-slate-950/40 p-3 text-xs text-slate-400 md:grid-cols-4">
              <ReportMetric label={evalResult.mode === 'chat' ? t('docs.chatPass') : t('docs.passRate')} value={`${Math.round(evalResult.pass_rate * 100)}%`} />
              <ReportMetric label={t('docs.cases')} value={`${evalResult.passed_count}/${evalResult.case_count}`} />
              <ReportMetric label={evalResult.mode === 'chat' ? t('docs.citedHit') : t('docs.sourceHit')} value={`${Math.round((evalResult.cited_source_hit_rate ?? evalResult.source_hit_rate) * 100)}%`} />
              <ReportMetric label={evalResult.mode === 'chat' ? t('docs.answerAvg') : t('docs.termAvg')} value={`${Math.round((evalResult.answer_term_coverage_avg ?? evalResult.term_coverage_avg) * 100)}%`} />
            </div>
            <FailureAnalysisPanel analysis={failureAnalysis} />
            <EvalRunDetails evalResult={evalResult} onUpdateCase={handleUpdateEvalCase} />
          </>
        )}
      </div>

      {SHOW_GLOSSARY_PANEL && <GlossaryPanel gameId={gameId} />}

      {documents.length > 0 && (
        <div className="space-y-2">
          {documents.map((doc) => (
            <div key={doc.id} className="card p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <FileText size={20} className="shrink-0 text-sky-300" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-slate-100">{doc.filename}</p>
                    <p className="text-xs text-slate-500">
                      {t('docs.pagesSize', { pages: doc.pages, size: (doc.file_size / 1024 / 1024).toFixed(2) })}
                    </p>
                  </div>
                  <span className="badge-success">{doc.status}</span>
                </div>
                <button
                  onClick={() => handleDeleteDocument(doc.id)}
                  className="btn-danger ml-2 p-2"
                >
                  <Trash2 size={18} />
                </button>
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  {t('docs.source')}
                  <select
                    value={doc.source_type || 'official_rulebook'}
                    onChange={(event) => handleUpdateDocumentSourceType(doc.id, event.target.value)}
                    className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200"
                  >
                    {DOCUMENT_SOURCE_TYPES.map((type) => (
                      <option key={type} value={type}>{t(`sourceType.${type}`)}</option>
                    ))}
                  </select>
                </label>
                <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => handleRebuildReport(doc.id)}
                  disabled={rebuildingReportId === doc.id || reprocessingId === doc.id}
                  className="steam-ghost px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {rebuildingReportId === doc.id ? <Loader size={14} className="animate-spin" /> : null}
                  {t('docs.rebuildReport')}
                </button>
                <button
                  type="button"
                  onClick={() => handleReprocess(doc.id)}
                  disabled={reprocessingId === doc.id || rebuildingReportId === doc.id}
                  className="steam-action px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {reprocessingId === doc.id ? <Loader size={14} className="animate-spin" /> : null}
                  {t('docs.reprocess')}
                </button>
                </div>
              </div>
              <ProcessingReportSummary
                report={doc.processing_report}
                documentId={doc.id}
                onOpenLayout={onOpenLayout}
              />
              <ChunkInspector documentId={doc.id} onChanged={loadDocuments} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

