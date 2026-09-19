// Registration is independent of all financial clients and credentials.
export function registerSenseEdgeWorker(production: boolean) {
  if (!production || !window.isSecureContext || !('serviceWorker' in navigator)) return;
  const register = () => { void navigator.serviceWorker.register('/senseedge-sw.js', {scope: '/', updateViaCache: 'none'}).catch(() => {
    // Website stays usable; installation/offline support is optional. Never log runtime context.
  }); };
  if (document.readyState === 'complete') register();
  else window.addEventListener('load', register, {once: true});
}
