"use client";

import { useState } from "react";
import { MessageCircle, Send } from "lucide-react";
import { askQuestion } from "@/lib/api";
import { ChatMessage } from "@/lib/types";
import Card from "./Card";
import Spinner from "./Spinner";

export default function ChatPanel({ documentId }: { documentId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleAsk() {
    const trimmed = question.trim();
    if (!trimmed) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setQuestion("");
    setLoading(true);

    try {
      const answer = await askQuestion(documentId, trimmed);
      setMessages((prev) => [...prev, { role: "assistant", content: answer }]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I couldn't answer that." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card icon={MessageCircle} title="Ask about this document">
      <div className="space-y-3 max-h-64 overflow-y-auto">
        {messages.length === 0 && (
          <p className="text-sm text-slate-400 dark:text-slate-500">
            Ask a question like &quot;What is the total amount?&quot;
          </p>
        )}

        {messages.map((message, i) => (
          <div
            key={i}
            className={`flex animate-fade-in ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${
                message.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200"
              }`}
            >
              {message.content}
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          placeholder="Type your question..."
          className="flex-1 border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 rounded-lg px-3 py-2 text-sm"
        />
        <button
          onClick={handleAsk}
          disabled={!question.trim() || loading}
          className="flex items-center justify-center px-3 py-2 bg-blue-600 text-white rounded-lg disabled:bg-slate-300 dark:disabled:bg-slate-700 hover:bg-blue-700 transition-colors"
        >
          {loading ? <Spinner /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </Card>
  );
}
