import { useAppStore } from '../store/AppStore'

export function Toasts() {
  const { toasts, dismissToast } = useAppStore()
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`} onClick={() => dismissToast(t.id)} role="status">
          {t.message}
        </div>
      ))}
    </div>
  )
}

