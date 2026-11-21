// The desktop bridge identifies retail builds. Browser and training installations retain the full toolset.
export const steamEdition = globalThis.window?.rovDesktop?.edition === 'steam';
