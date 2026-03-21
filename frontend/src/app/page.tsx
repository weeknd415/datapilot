"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage } from "@/components/ChatMessage";
import { AgentTrace } from "@/components/AgentTrace";
import { Header } from "@/components/Header";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  confidence?: number;
  sources?: Array<{ source_type: string; source_name: string; details: string }>;
  trace?: Array<{
    agent: string;
    action: string;
    input_summary: string;
    output_summary: string;
    confidence: number;
    duration_ms: number;
  }>;
  duration_ms?: number;
  status?: string;
  chart_base64?: string;
}

const EXAMPLE_QUERIES = [
  "What are the top 5 customers by total revenue?",
  "Show monthly revenue trends for 2024",
  "Which products have the highest profit margins?",
  "How many overdue invoices do we have and what's the total amount?",
  "Compare Q3 vs Q4 2024 revenue by product category",
  "What's the average order value by customer tier?",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedTrace, setSelectedTrace] = useState<Message["trace"]>([]);
  const [showTrace, setShowTrace] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendQuery = async (query: string) => {
    if (!query.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: query,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, include_trace: true }),
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);

      const data = await response.json();

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.answer || "I could not generate an answer.",
        confidence: data.confidence,
        sources: data.sources,
        trace: data.trace,
        duration_ms: data.duration_ms,
        status: data.status,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setSelectedTrace(data.trace || []);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Connection error. Make sure the backend is running at ${API_URL}. Error: ${error}`,
        status: "failed",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendQuery(input);
  };

  return (
    <div className="flex h-screen bg-[#0a0a0a]">
      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 min-w-0">
        <Header
          showTrace={showTrace}
          onToggleTrace={() => setShowTrace(!showTrace)}
        />

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 ? (
            <div className="max-w-2xl mx-auto mt-20">
              <h2 className="text-3xl font-bold text-center mb-2 bg-gradient-to-r from-primary-400 to-primary-600 bg-clip-text text-transparent">
                DataPilot
              </h2>
              <p className="text-gray-400 text-center mb-8">
                Ask questions about your business data in plain English.
                I'll query databases, search documents, and generate
                analytics.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {EXAMPLE_QUERIES.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => sendQuery(q)}
                    className="text-left px-4 py-3 rounded-lg border border-gray-800 hover:border-primary-500 hover:bg-gray-900 transition-colors text-sm text-gray-300"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-6">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onSelectTrace={() => {
                    if (msg.trace) {
                      setSelectedTrace(msg.trace);
                      setShowTrace(true);
                    }
                  }}
                />
              ))}
              {isLoading && (
                <div className="flex items-center gap-3 text-gray-400">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-primary-500 rounded-full animate-bounce [animation-delay:0ms]" />
                    <span className="w-2 h-2 bg-primary-500 rounded-full animate-bounce [animation-delay:150ms]" />
                    <span className="w-2 h-2 bg-primary-500 rounded-full animate-bounce [animation-delay:300ms]" />
                  </div>
                  <span className="text-sm">Agents working...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-gray-800 p-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about your business data..."
                className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="px-6 py-3 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg font-medium transition-colors"
              >
                Send
              </button>
            </div>
            <p className="text-xs text-gray-600 mt-2 text-center">
              Powered by LangGraph + Groq (Llama 3.3 70B) | Agents: SQL,
              Document, Analytics
            </p>
          </form>
        </div>
      </div>

      {/* Agent Trace Panel */}
      {showTrace && (
        <div className="w-80 border-l border-gray-800 bg-[#0d0d1a] overflow-y-auto">
          <AgentTrace steps={selectedTrace} />
        </div>
      )}
    </div>
  );
}
