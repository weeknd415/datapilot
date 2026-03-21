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
  chart_type?: string;
}

interface UploadedFile {
  filename: string;
  chunks: number;
  timestamp: string;
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
  const [isUploading, setIsUploading] = useState(false);
  const [selectedTrace, setSelectedTrace] = useState<Message["trace"]>([]);
  const [showTrace, setShowTrace] = useState(true);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [showUploadPanel, setShowUploadPanel] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
        chart_base64: data.chart_base64,
        chart_type: data.chart_type,
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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch(`${API_URL}/api/upload`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) throw new Error(`Upload failed: ${response.status}`);

        const data = await response.json();

        setUploadedFiles((prev) => [
          ...prev,
          {
            filename: data.filename,
            chunks: data.chunks_created,
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);

        // Add a system message about the upload
        const uploadMsg: Message = {
          id: Date.now().toString(),
          role: "assistant",
          content: `Document uploaded: **${data.filename}** (${data.chunks_created} chunks indexed). You can now ask questions about this document.`,
          status: "completed",
        };
        setMessages((prev) => [...prev, uploadMsg]);
      } catch (error) {
        const errorMsg: Message = {
          id: Date.now().toString(),
          role: "assistant",
          content: `Failed to upload ${file.name}: ${error}`,
          status: "failed",
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
    }

    setIsUploading(false);
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
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
          uploadedCount={uploadedFiles.length}
          onToggleUpload={() => setShowUploadPanel(!showUploadPanel)}
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

              {/* Upload prompt */}
              <div className="mb-6 p-4 rounded-lg border border-dashed border-gray-700 bg-gray-900/50 text-center">
                <p className="text-sm text-gray-400 mb-3">
                  Upload documents (PDF, TXT, CSV) to enable the Document Agent
                </p>
                <label className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm rounded-lg cursor-pointer transition-colors">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  Upload Documents
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.txt,.md,.csv"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                </label>
              </div>

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
              {isUploading && (
                <div className="flex items-center gap-3 text-amber-400">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-amber-500 rounded-full animate-bounce [animation-delay:0ms]" />
                    <span className="w-2 h-2 bg-amber-500 rounded-full animate-bounce [animation-delay:150ms]" />
                    <span className="w-2 h-2 bg-amber-500 rounded-full animate-bounce [animation-delay:300ms]" />
                  </div>
                  <span className="text-sm">Uploading and indexing document...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input bar */}
        <div className="border-t border-gray-800 p-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="flex gap-3">
              {/* Upload button */}
              <label className="flex items-center justify-center w-12 h-12 bg-gray-900 border border-gray-700 rounded-lg cursor-pointer hover:border-amber-500 hover:bg-gray-800 transition-colors group">
                <svg className="w-5 h-5 text-gray-500 group-hover:text-amber-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.txt,.md,.csv"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>

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

      {/* Right Panel: Agent Trace or Uploaded Files */}
      {(showTrace || showUploadPanel) && (
        <div className="w-80 border-l border-gray-800 bg-[#0d0d1a] overflow-y-auto">
          {showUploadPanel ? (
            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-300">
                  Uploaded Documents
                </h3>
                <button
                  onClick={() => setShowUploadPanel(false)}
                  className="text-xs text-gray-500 hover:text-gray-300"
                >
                  Close
                </button>
              </div>
              {uploadedFiles.length === 0 ? (
                <p className="text-xs text-gray-600">
                  No documents uploaded yet. Click the paperclip icon or the
                  upload button to add documents for the Document Agent.
                </p>
              ) : (
                <div className="space-y-2">
                  {uploadedFiles.map((file, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-lg bg-gray-900 border border-gray-800"
                    >
                      <div className="flex items-start gap-2">
                        <svg className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <div className="min-w-0">
                          <p className="text-sm text-gray-200 truncate">
                            {file.filename}
                          </p>
                          <p className="text-xs text-gray-500">
                            {file.chunks} chunks | {file.timestamp}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <AgentTrace steps={selectedTrace} />
          )}
        </div>
      )}
    </div>
  );
}
