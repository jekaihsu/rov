// Internal-edition gate for the company training mode. Steam builds set
// window.rovDesktop.edition === 'steam' and must not show this mode on the main line.
export function isInternalEdition(host = globalThis) {
  const desktop = host?.window?.rovDesktop ?? host?.rovDesktop;
  return desktop?.edition !== 'steam';
}
