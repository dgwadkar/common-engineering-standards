#!/usr/bin/env node
// @org/standards-sync — npx entrypoint.
//
// Stays tiny intentionally — delegates to src/cli.js so the same surface is testable
// without spawning a subprocess.

import { runCli } from "../src/cli.js";

runCli(process.argv).then(
  (code) => process.exit(code ?? 0),
  (err) => {
    // Last-resort: anything that escapes runCli's try/catch lands here. Print the stack
    // so operators have a real diagnostic to file a bug with.
    console.error(err && err.stack ? err.stack : err);
    process.exit(1);
  },
);
