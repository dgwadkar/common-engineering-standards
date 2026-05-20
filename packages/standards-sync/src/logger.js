// @org/standards-sync — pluggable logger.
//
// Phase 8 lesson: every Phase-7 release-helper supports `--dry-run` and prints a structured
// summary. The consumer-side CLI mirrors that by emitting one line per meaningful step (with
// level prefix) so users can scan a sync run without flag-flipping into verbose mode. The
// `--quiet` flag suppresses INFO and DEBUG, leaving only WARN and ERROR.
//
// The logger is intentionally a tiny struct of functions, not a class — the CLI passes it
// through as a plain object so tests can swap in a recording sink without monkey-patching.

const LEVELS = Object.freeze({ debug: 10, info: 20, warn: 30, error: 40 });

export function createLogger({ level = "info", sink = console } = {}) {
  const threshold = LEVELS[level] ?? LEVELS.info;
  const emit = (severity, prefix, args) => {
    if (LEVELS[severity] < threshold) return;
    const out = severity === "error" || severity === "warn" ? sink.error : sink.log;
    out.call(sink, `[${prefix}]`, ...args);
  };
  return {
    debug: (...args) => emit("debug", "debug", args),
    info: (...args) => emit("info", "info", args),
    warn: (...args) => emit("warn", "warn", args),
    error: (...args) => emit("error", "error", args),
    success: (...args) => emit("info", " ok ", args),
  };
}

// A recording logger for tests — captures every call as a `{level, args}` record.
export function createRecordingLogger() {
  const records = [];
  const make = (level) => (...args) => records.push({ level, args });
  return {
    records,
    debug: make("debug"),
    info: make("info"),
    warn: make("warn"),
    error: make("error"),
    success: make("success"),
  };
}
