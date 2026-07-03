import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Frontend render error', error, info)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-6">
        <div className="max-w-2xl w-full rounded-lg border border-red-400/40 bg-red-950/40 p-5 shadow-xl">
          <p className="text-xs uppercase tracking-wide text-red-200 mb-2">Frontend fejl</p>
          <h1 className="text-xl font-semibold mb-3">TimeLapse Pro kunne ikke rendere siden</h1>
          <pre className="text-sm whitespace-pre-wrap rounded bg-black/40 p-3 text-red-100 overflow-auto">
            {this.state.error.message}
          </pre>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 rounded bg-white text-slate-900 text-sm font-medium"
          >
            Genindlæs
          </button>
        </div>
      </div>
    )
  }
}
