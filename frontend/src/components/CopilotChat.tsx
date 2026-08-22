import { useEffect, useRef, useState } from "react";
import { ApiError, api } from "../lib/api";
import type { ChatMessage } from "../lib/types";

const SUGGESTIONS = [
  "Can I spend ₹700 on dinner tonight?",
  "Where is my money going this month?",
  "Am I going to overspend?",
];

export default function CopilotChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function send(text?: string) {
    const trimmed = (text ?? input).trim();
    if (!trimmed || loading) return;

    const history = messages;
    setMessages([...history, { role: "user", content: trimmed }]);
    setInput("");
    setError(null);
    setLoading(true);
    try {
      const res = await api.chat(trimmed, history);
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
    } catch (e) {
      // Drop the optimistic user message back into the box so it isn't lost.
      setMessages(history);
      setInput(trimmed);
      setError(
        e instanceof ApiError
          ? e.message
          : "Couldn't reach the copilot. Is LLM_API_KEY set on the backend?",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-ink-800 rounded-xl p-5">
      <p className="text-sm text-paper/60 mb-3">SpendShield Copilot</p>

      <div ref={scrollRef} className="space-y-2 mb-3 max-h-64 overflow-y-auto">
        {messages.length === 0 && !loading && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="text-xs text-paper/60 border border-ink-700 rounded-full px-3 py-1.5 hover:border-marigold-500 hover:text-paper"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-sm rounded-lg px-3 py-2 max-w-[85%] whitespace-pre-wrap ${
              m.role === "user"
                ? "bg-marigold-500/15 text-paper ml-auto"
                : "bg-ink-900 text-paper/90"
            }`}
          >
            {m.content}
          </div>
        ))}

        {loading && (
          <div className="bg-ink-900 text-paper/50 text-sm rounded-lg px-3 py-2 max-w-[85%]">
            Checking your numbers…
          </div>
        )}
      </div>

      {error && <p role="alert" className="text-sindoor-500 text-sm mb-2">{error}</p>}

      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about your money…"
          aria-label="Message the copilot"
          className="flex-1 bg-ink-900 rounded-lg px-3 py-2 text-sm text-paper outline-none border border-ink-700 focus:border-marigold-500"
        />
        <button
          onClick={() => send()}
          disabled={loading || !input.trim()}
          className="bg-marigold-500 hover:bg-marigold-600 disabled:opacity-50 text-ink-950 font-medium text-sm rounded-lg px-4 py-2"
        >
          Send
        </button>
      </div>

      <p className="text-xs text-paper/30 mt-2">
        Every figure the copilot quotes comes from the same engine as your dashboard —
        it explains numbers, it never invents them.
      </p>
    </div>
  );
}
