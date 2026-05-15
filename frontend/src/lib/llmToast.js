// LLM progress toast wrapper.
// Shows a long "Generating with real LLM…" toast when USE_REAL_LLM_PROVIDER is on,
// otherwise stays out of the way and lets the caller's own toasts run.
import { toast } from "sonner";
import { FeatureFlags } from "../lib/api";

let _flagsPromise = null;
let _flagsCache = null;
let _flagsAt = 0;
const FLAGS_TTL_MS = 30_000;

async function _isRealLLMOn() {
  const now = Date.now();
  if (_flagsCache && now - _flagsAt < FLAGS_TTL_MS) return !!_flagsCache.llm;
  if (!_flagsPromise) {
    _flagsPromise = FeatureFlags.get()
      .then((f) => {
        _flagsCache = f || {};
        _flagsAt = Date.now();
        return _flagsCache;
      })
      .catch(() => ({}))
      .finally(() => {
        _flagsPromise = null;
      });
  }
  const f = await _flagsPromise;
  return !!(f && f.llm);
}

/**
 * Force a refresh of the feature flag cache (e.g. after the Providers tab
 * toggles the mode). Optional.
 */
export function invalidateLLMFlagCache() {
  _flagsCache = null;
  _flagsAt = 0;
}

/**
 * Wraps an async creative call with a real-LLM progress toast.
 *
 *   opName          short verb like "rewrite" / "improve" / "enhance image prompt"
 *   fn              () => Promise<{ llm_mode?, llm_status?, llm_duration_ms?, ... }>
 *   options.testId  data-testid for the sonner toast id (e.g. "llm-toast-rewrite")
 *
 * Behavior:
 *   - If USE_REAL_LLM_PROVIDER=true:
 *       Loading: "Generating with real LLM…"
 *       Success (llm_mode==='real'): "Real LLM completed in {duration}s"
 *       Success (llm_status==='fallback'): "Real LLM failed, mock fallback used"
 *       Error: "Generation failed. Please try again."
 *   - If USE_REAL_LLM_PROVIDER=false: just runs fn() with no extra toast.
 *     (Callers handle their own short success/failure toasts.)
 */
export async function withRealLLMToast(opName, fn, { testId } = {}) {
  const isReal = await _isRealLLMOn();
  if (!isReal) {
    return fn();
  }
  const startedAt = performance.now();
  const id = testId || `llm-toast-${opName}`;
  const tid = toast.loading(`Generating with real LLM…`, {
    id,
    description: `Working on ${opName}. Real models can take 15–120 s.`,
    duration: Infinity,
  });
  try {
    const result = await fn();
    const serverMs = Number(result?.llm_duration_ms) || 0;
    const elapsedMs = Math.round(performance.now() - startedAt);
    const ms = serverMs > 0 ? serverMs : elapsedMs;
    const seconds = (ms / 1000).toFixed(1);
    if (result?.llm_status === "fallback") {
      toast.warning("Real LLM failed, mock fallback used", {
        id: tid,
        description: `Switched to the deterministic mock after ${seconds}s.`,
        duration: 5000,
      });
    } else if (result?.llm_mode === "real" && result?.llm_status === "success") {
      toast.success(`Real LLM completed in ${seconds}s`, {
        id: tid,
        description: `${opName} done · mode=real.`,
        duration: 4500,
      });
    } else {
      // Flag is on but the call ran in mock (e.g. blocked / key missing).
      toast.success(`${opName} done`, {
        id: tid,
        description: `Ran in mock mode · ${seconds}s.`,
        duration: 3500,
      });
    }
    return result;
  } catch (err) {
    toast.error("Generation failed. Please try again.", {
      id: tid,
      description: err?.message || "Unknown error.",
      duration: 6000,
    });
    throw err;
  }
}
