"use client";

import { useState } from "react";

import { useSendChatMessage } from "@/lib/queries/useChat";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

const EXAMPLE_QUESTIONS = [
  "Wie hat sich mein Vermögen diesen Monat entwickelt?",
  "Wie hoch ist mein BTC-Anteil?",
  "Wie viel Cash habe ich?",
  "Warum ist der BTC Score heute niedriger?",
];

interface Message {
  role: "user" | "assistant";
  text: string;
  dataUsed?: Record<string, unknown> | null;
  error?: string | null;
}

export function ChatWindow() {
  const send = useSendChatMessage();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");

  async function handleSend(question?: string) {
    const message = (question ?? input).trim();
    if (!message) return;

    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setInput("");

    const result = await send.mutateAsync(message);
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        text: result.reply ?? (result.error ? `Fehler: ${result.error}` : "Keine Antwort erhalten."),
        dataUsed: result.data_used,
        error: result.error,
      },
    ]);
  }

  return (
    <div className="flex h-[70vh] flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-slate-500">Beispiel-Fragen:</p>
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                className="block w-full rounded-lg bg-slate-50 px-3 py-2 text-left text-sm text-slate-600 hover:bg-slate-100"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${
                message.role === "user" ? "bg-slate-900 text-white" : "bg-slate-50 text-slate-800"
              }`}
            >
              <p>{message.text}</p>
              {message.dataUsed && (
                <details className="mt-1 text-xs opacity-70">
                  <summary className="cursor-pointer">verwendete Daten</summary>
                  <pre className="mt-1 overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(message.dataUsed, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          </div>
        ))}

        {send.isPending && <p className="text-xs text-slate-400">Antwort wird erstellt…</p>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="flex gap-2 border-t border-slate-200 p-3"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Frage stellen…"
          disabled={send.isPending}
        />
        <Button type="submit" disabled={send.isPending || !input.trim()}>
          Senden
        </Button>
      </form>
    </div>
  );
}
