import * as React from 'react'
import { ping } from '@/lib/api'

/**
 * Probe backend `/healthz` on mount (and on `retry()` call).
 *
 * A2 acceptance: App mount → call ping() → if false, set backendDown=true
 * so <BackendDownBanner /> displays the recovery hint.
 *
 * Returns: { backendDown, checking, retry } — retry() lets the user manually
 * re-probe after starting the backend.
 */
export function useHealthz() {
  const [backendDown, setBackendDown] = React.useState(false)
  const [checking, setChecking] = React.useState(true)

  const probe = React.useCallback(async () => {
    setChecking(true)
    const ok = await ping()
    setBackendDown(!ok)
    setChecking(false)
  }, [])

  React.useEffect(() => {
    // setState-in-effect is intentional: probe on mount.
    // React 19's stricter set-state-in-effect rule misfires here — useEffect is
    // the correct place to kick a one-shot async side effect on mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    probe()
  }, [probe])

  return { backendDown, checking, retry: probe }
}
