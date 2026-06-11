import React from 'react'
import { Eye, EyeOff, Save, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { settingsAPI } from '../api/client'
import { useI18n } from '../i18n'

const emptyConfig = {
  chat: { api_base: '', api_key: '', model: '', thinking_enabled: false, reasoning_effort: 'high' },
  embedding: { api_base: '', api_key: '', model: '' },
  rerank: { enabled: false, model: 'Qwen/Qwen3-VL-Reranker-8B', candidates: 30, top_n: 8 },
}

export default function ModelSettings({ open, onClose }) {
  const { t } = useI18n()
  const [config, setConfig] = React.useState(emptyConfig)
  const [loading, setLoading] = React.useState(false)
  const [saving, setSaving] = React.useState(false)
  const [showKeys, setShowKeys] = React.useState(false)

  React.useEffect(() => {
    if (!open) return

    const loadConfig = async () => {
      setLoading(true)
      try {
        const response = await settingsAPI.getModelConfig()
        setConfig(response.data)
      } catch (error) {
        toast.error(t('toast.modelLoadFailed'))
      } finally {
        setLoading(false)
      }
    }

    loadConfig()
  }, [open])

  const updateField = (section, field, value) => {
    setConfig((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [field]: value,
      },
    }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const nextConfig = {
        ...config,
        chat: {
          ...config.chat,
          thinking_enabled: false,
          reasoning_effort: config.chat?.reasoning_effort || 'high',
        },
      }
      const response = await settingsAPI.updateModelConfig(nextConfig)
      setConfig(response.data)
      toast.success(t('toast.modelSaved'))
      onClose()
    } catch (error) {
      const message = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : t('toast.modelSaveFailed')
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  const keyInputType = showKeys ? 'text' : 'password'

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/70 px-4 py-8">
      <form onSubmit={handleSubmit} className="w-full max-w-3xl rounded-lg border border-slate-700 bg-slate-900 shadow-2xl shadow-black/40">
        <div className="flex items-center justify-between border-b border-slate-700 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">{t('model.title')}</h2>
            <p className="text-sm text-slate-500">{t('model.desc')}</p>
          </div>
          <button type="button" onClick={onClose} className="btn-secondary p-2" aria-label={t('model.close')}>
            <X size={18} />
          </button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="flex h-48 items-center justify-center">
              <div className="h-10 w-10 animate-spin rounded-full border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-2">
              <ProviderFields
                title={t('model.chat')}
                section="chat"
                config={config.chat}
                keyInputType={keyInputType}
                onChange={updateField}
              />
              <ProviderFields
                title={t('model.embedding')}
                section="embedding"
                config={config.embedding}
                keyInputType={keyInputType}
                onChange={updateField}
              />
              <RerankFields
                config={config.rerank || emptyConfig.rerank}
                onChange={updateField}
              />
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-slate-700 px-6 py-4">
          <button
            type="button"
            onClick={() => setShowKeys((value) => !value)}
            className="btn-secondary flex items-center gap-2"
          >
            {showKeys ? <EyeOff size={18} /> : <Eye size={18} />}
            {showKeys ? t('model.hideKeys') : t('model.showKeys')}
          </button>
          <div className="flex gap-2">
            <button type="button" onClick={onClose} className="btn-secondary">
              {t('model.cancel')}
            </button>
            <button type="submit" disabled={saving || loading} className="btn-primary flex items-center gap-2 disabled:opacity-60">
              <Save size={18} />
              {saving ? t('model.saving') : t('model.save')}
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}

function RerankFields({ config, onChange }) {
  const { t } = useI18n()

  return (
    <section className="space-y-4 md:col-span-2">
      <div>
        <h3 className="text-base font-semibold text-slate-100">{t('model.rerank')}</h3>
        <p className="mt-1 text-xs text-slate-500">
          {t('model.rerankDesc')}
        </p>
      </div>
      <label className="inline-flex items-center gap-2 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={Boolean(config.enabled)}
          onChange={(event) => onChange('rerank', 'enabled', event.target.checked)}
        />
        {t('model.enableReranker')}
      </label>
      <div className="grid gap-4 md:grid-cols-3">
        <label className="block space-y-1 md:col-span-1">
          <span className="text-sm font-medium text-slate-300">{t('model.model')}</span>
          <input
            className="input"
            value={config.model}
            onChange={(event) => onChange('rerank', 'model', event.target.value)}
            placeholder="Qwen/Qwen3-VL-Reranker-8B"
            required
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm font-medium text-slate-300">{t('model.candidates')}</span>
          <input
            className="input"
            type="number"
            min="8"
            max="80"
            value={config.candidates}
            onChange={(event) => onChange('rerank', 'candidates', Number.parseInt(event.target.value, 10) || 30)}
            required
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm font-medium text-slate-300">{t('model.topN')}</span>
          <input
            className="input"
            type="number"
            min="1"
            max="30"
            value={config.top_n}
            onChange={(event) => onChange('rerank', 'top_n', Number.parseInt(event.target.value, 10) || 8)}
            required
          />
        </label>
      </div>
    </section>
  )
}

function ProviderFields({ title, section, config, keyInputType, onChange }) {
  const { t } = useI18n()

  return (
    <section className="space-y-4">
      <h3 className="text-base font-semibold text-slate-100">{title}</h3>
      <label className="block space-y-1">
        <span className="text-sm font-medium text-slate-300">{t('model.baseUrl')}</span>
        <input
          className="input"
          value={config.api_base}
          onChange={(event) => onChange(section, 'api_base', event.target.value)}
          placeholder="https://api.openai.com/v1"
          required
        />
      </label>
      <label className="block space-y-1">
        <span className="text-sm font-medium text-slate-300">{t('model.apiKey')}</span>
        <input
          className="input"
          type={keyInputType}
          value={config.api_key}
          onChange={(event) => onChange(section, 'api_key', event.target.value)}
          placeholder="sk-..."
        />
      </label>
      <label className="block space-y-1">
        <span className="text-sm font-medium text-slate-300">{t('model.model')}</span>
        <input
          className="input"
          value={config.model}
          onChange={(event) => onChange(section, 'model', event.target.value)}
          placeholder={t('model.modelName')}
          required
        />
      </label>
    </section>
  )
}
