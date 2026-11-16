/**
 * Node.js ES module loader hook for importing `.glsl` shader files as default strings.
 *
 * Uses synchronous `module.registerHooks` on Node 22.15+ / 24+ / 26+ (zero warnings,
 * zero worker-thread overhead) and falls back to `module.register` on Node 20.6–22.14.
 */

import { readFileSync } from "node:fs";
import * as moduleNs from "node:module";
import { fileURLToPath } from "node:url";

const GLSL_EXTENSION = ".glsl";
const LEGACY_ASYNC_HOOK_SOURCE = [
  'import { readFile } from "node:fs/promises";',
  'import { fileURLToPath } from "node:url";',
  "export async function load(url, context, nextLoad) {",
  '  if (url.endsWith(".glsl")) {',
  '    const raw = await readFile(fileURLToPath(url), "utf8");',
  "    return {",
  '      format: "module",',
  "      shortCircuit: true,",
  '      source: "export default " + JSON.stringify(raw) + ";\\n",',
  "    };",
  "  }",
  "  return nextLoad(url, context);",
  "}",
].join("\n");

let isRegistered = false;

/**
 * Register the `.glsl` ES module source loader once per Node process.
 *
 * @returns {void}
 */
export function registerGlslModuleHooks() {
  if (isRegistered) {
    return;
  }
  isRegistered = true;

  if (typeof moduleNs.registerHooks === "function") {
    moduleNs.registerHooks({
      load(url, context, nextLoad) {
        if (url.endsWith(GLSL_EXTENSION)) {
          const raw = readFileSync(fileURLToPath(url), "utf8");
          return {
            format: "module",
            shortCircuit: true,
            source: `export default ${JSON.stringify(raw)};\n`,
          };
        }
        return nextLoad(url, context);
      },
    });
    return;
  }

  if (typeof moduleNs.register === "function") {
    moduleNs.register(`data:text/javascript,${encodeURIComponent(LEGACY_ASYNC_HOOK_SOURCE)}`);
  }
}

registerGlslModuleHooks();
