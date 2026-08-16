export function AiUnavailableBanner() {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
      Der KI-Assistent ist nicht konfiguriert (kein <code className="rounded bg-amber-100 px-1">ANTHROPIC_API_KEY</code>{" "}
      hinterlegt). Trage den Key in der Backend-<code className="rounded bg-amber-100 px-1">.env</code>-Datei ein, um
      diese Funktion zu nutzen.
    </div>
  );
}
