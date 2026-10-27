// The local editor can receive plain-text errors from the server or dev proxy.
export async function readEditResponse(response) {
  const raw = await response.text();
  let result;
  try { result = raw ? JSON.parse(raw) : null; } catch { /* handled below */ }
  if (!response.ok) {
    const message = typeof result?.detail === 'string' ? result.detail
      : response.status >= 500
        ? `The server could not complete this request (HTTP ${response.status}). Please try again.`
        : `Request failed (HTTP ${response.status}). Please check your input and try again.`;
    throw new Error(message);
  }
  if (result === undefined || (result === null && response.status !== 204)) {
    throw new Error('The server returned an unexpected response. Refresh the page and try again.');
  }
  return result;
}
