// Node module-resolution hooks: map the browser import map ("three", "three/addons/...") onto the vendored
// three.js, so viewer modules can be imported unchanged by Node tools and tests.
//   import {register} from 'node:module';
//   register('./three_resolve_hooks.mjs', import.meta.url);
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const vendor = path.resolve(here, '..', 'viewer', 'vendor', 'three');

export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'three') {
    return {url: pathToFileURL(path.join(vendor, 'build', 'three.module.js')).href, shortCircuit: true};
  }
  if (specifier.startsWith('three/addons/')) {
    const rest = specifier.slice('three/addons/'.length);
    return {url: pathToFileURL(path.join(vendor, 'examples', 'jsm', rest)).href, shortCircuit: true};
  }
  return nextResolve(specifier, context);
}
