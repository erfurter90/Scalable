"use client";

import { useChatStatus } from "@/lib/queries/useChat";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { AiUnavailableBanner } from "@/components/chat/AiUnavailableBanner";

export default function ChatPage() {
  const status = useChatStatus();

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Ask my Financial Assistant</h1>
      <p className="text-sm text-slate-500">
        Der Assistent beantwortet Fragen ausschließlich anhand bereits berechneter Daten aus deinem Dashboard — er
        schätzt oder erfindet keine Zahlen.
      </p>

      {status.isLoading ? (
        <p className="text-sm text-slate-500">Prüfe Verfügbarkeit…</p>
      ) : status.data?.configured ? (
        <ChatWindow />
      ) : (
        <AiUnavailableBanner />
      )}
    </div>
  );
}
