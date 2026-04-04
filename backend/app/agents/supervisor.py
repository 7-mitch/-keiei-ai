"use client";
import dynamic from "next/dynamic";
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });
import { useState, useRef, useEffect } from "react";
import { chatApi, ChatResponse, api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";

interface Message {
  role:          "user" | "ai";
  content:       string;
  route?:        string;
  file?:         string;
  graph_base64?: string;
  graph_json?:   string;
  session_id?:   string;
  question?:     string;
  feedback?:     "good" | "bad";
  latency_ms?:   number;
  mode?:         string;
}

const routeColor: Record<string, string> = {
  sql:           "bg-blue-100 text-blue-800",
  rag:           "bg-purple-100 text-purple-800",
  fraud:         "bg-red-100 text-red-800",
  web:           "bg-green-100 text-green-800",
  general:       "bg-gray-100 text-gray-800",
  hr:            "bg-yellow-100 text-yellow-800",
  cash_flow:     "bg-emerald-100 text-emerald-800",
  project:       "bg-orange-100 text-orange-800",
  file_analysis: "bg-sky-100 text-sky-800",
};

const routeLabel: Record<string, string> = {
  sql:           "データ分析",
  rag:           "社内文書検索",
  fraud:         "不正検知",
  web:           "Web収集",
  general:       "一般",
  hr:            "人事",
  cash_flow:     "資金繰り",
  project:       "工程管理",
  file_analysis: "ファイル解析",
};

const MODES = [
  { id: "standard",  label: "標準",    description: "日常会話・補助金検索",   model: "gemma3:4b", temperature: 0.7, top_p: 0.9, color: "bg-blue-500"    },
  { id: "analysis",  label: "詳細分析", description: "財務分析・レポート作成", model: "gemma3:4b", temperature: 0.3, top_p: 0.8, color: "bg-emerald-500" },
  { id: "reasoning", label: "推論",    description: "戦略立案・複雑な判断",   model: "qwen3:8b",  temperature: 0.1, top_p: 0.7, color: "bg-purple-500"  },
  { id: "expert",    label: "専門家",  description: "法的判断・最高精度",     model: "qwen3:8b",  temperature: 0.0, top_p: 0.5, color: "bg-red-500"     },
];

const ACCEPT_TYPES = ".pdf,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.docx,.doc";

export default function ChatPage() {
  const [messages,     setMessages]     = useState<Message[]>([
    {
      role:    "ai",
      content: "こんにちは。経営に関するご質問をどうぞ。\n例: 「今月の取引件数は？」「補助金について教えて」",
    },
  ]);
  const [input,        setInput]        = useState("");
  const [loading,      setLoading]      = useState(false);
  const [file,         setFile]         = useState<File | null>(null);
  const [listening,    setListening]    = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [modeId,       setModeId]       = useState("standard");
  const [temperature,  setTemperature]  = useState(0.7);
  const [topP,         setTopP]         = useState(0.9);

  const fileRef        = useRef<HTMLInputElement>(null);
  const bottomRef      = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);

  const currentMode = MODES.find(m => m.id === modeId) || MODES[0];

  const handleModeChange = (id: string) => {
    const mode = MODES.find(m => m.id === id);
    if (mode) {
      setModeId(id);
      setTemperature(mode.temperature);
      setTopP(mode.top_p);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // ===== 音声認識 =====
  const startVoice = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("このブラウザは音声認識に対応していません。Chromeをお使いください。");
      return;
    }

    const recognition            = new SpeechRecognition();
    recognition.lang             = "ja-JP";
    recognition.interimResults   = false;
    recognition.maxAlternatives  = 1;
    recognition.onstart  = () => setListening(true);
    recognition.onerror  = () => setListening(false);
    recognition.onend    = () => setListening(false);
    recognition.onresult = (event: any) => {
      setInput(event.results[0][0].transcript);
      setListening(false);
    };
    recognitionRef.current = recognition;
    recognition.start();
  };

  const stopVoice = () => {
    recognitionRef.current?.stop();
    setListening(false);
  };

  // ===== フィードバック =====
  const sendFeedback = async (msgIndex: number, feedback: "good" | "bad") => {
    const msg = messages[msgIndex];
    if (!msg.session_id || msg.feedback) return;

    setMessages((prev) => prev.map((m, i) =>
      i === msgIndex ? { ...m, feedback } : m
    ));

    try {
      await api.post("/api/feedback", {
        session_id: msg.session_id,
        question:   msg.question || "",
        answer:     msg.content,
        route:      msg.route || "general",
        feedback,
        latency_ms: msg.latency_ms,
      });
    } catch (e) {
      console.error("フィードバック送信失敗", e);
    }
  };

  // ===== メッセージ送信 =====
  const sendMessage = async () => {
    if ((!input.trim() && !file) || loading) return;

    const question = input.trim() || `ファイル「${file?.name}」を分析してください`;
    const thinking = modeId === "reasoning" || modeId === "expert";

    setInput("");
    setMessages((prev) => [...prev, {
      role:    "user",
      content: question,
      file:    file?.name,
      mode:    modeId,
    }]);
    setLoading(true);
    const startTime = Date.now();

    try {
      let res: ChatResponse;

      if (file) {
        const formData = new FormData();
        formData.append("file",        file);
        formData.append("question",    question);
        formData.append("thinking",    String(thinking));
        formData.append("mode",        modeId);
        formData.append("temperature", String(temperature));
        formData.append("top_p",       String(topP));
        const response = await api.post("/api/chat/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        res = response.data;
      } else {
        // ★ mode / temperature / topP を渡す（修正箇所）
        res = await chatApi.send(question, thinking, modeId, temperature, topP);
      }

      const latency_ms = Date.now() - startTime;

      setMessages((prev) => [
        ...prev,
        {
          role:         "ai",
          content:      res.answer,
          route:        res.route,
          graph_base64: res.graph_base64 ?? undefined,
          graph_json:   res.graph_json   ?? undefined,  // ★ Plotly追加
          session_id:   res.session_id,
          question:     question,
          latency_ms,
          mode:         modeId,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: "エラーが発生しました。再度お試しください。" },
      ]);
    } finally {
      setLoading(false);
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 64px)" }}>

      {/* ヘッダー */}
      <div className="px-6 pt-6 pb-2 shrink-0">
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-3xl font-bold">AIアシスタント</h1>
        </div>

        {/* モード選択 */}
        <div className="flex gap-2 flex-wrap mb-2">
          {MODES.map((mode) => (
            <button
              key={mode.id}
              onClick={() => handleModeChange(mode.id)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                modeId === mode.id
                  ? `${mode.color} text-white shadow-md`
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {mode.label}
              {modeId === mode.id && (
                <span className="ml-1 text-xs opacity-75">({mode.model})</span>
              )}
            </button>
          ))}
        </div>

        <p className="text-xs text-muted-foreground mb-2">
          {currentMode.description}
        </p>

        {/* 詳細設定 */}
        <div className="border rounded-lg overflow-hidden">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full px-4 py-2 text-xs text-gray-500 flex items-center justify-between hover:bg-gray-50"
          >
            <span>詳細設定（temperature / top_p）</span>
            <span>{showAdvanced ? "▲" : "▼"}</span>
          </button>

          {showAdvanced && (
            <div className="px-4 py-3 bg-gray-50 space-y-3">
              <div>
                <div className="flex justify-between text-xs text-gray-600 mb-1">
                  <span>temperature（創造性）</span>
                  <span className="font-mono font-bold">{temperature.toFixed(2)}</span>
                </div>
                <input
                  type="range" min="0" max="1" step="0.05"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-blue-500"
                />
                <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                  <span>正確・固定</span>
                  <span>創造的・多様</span>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs text-gray-600 mb-1">
                  <span>top_p（語彙の多様性）</span>
                  <span className="font-mono font-bold">{topP.toFixed(2)}</span>
                </div>
                <input
                  type="range" min="0.1" max="1" step="0.05"
                  value={topP}
                  onChange={(e) => setTopP(parseFloat(e.target.value))}
                  className="w-full accent-blue-500"
                />
                <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                  <span>集中・絞り込み</span>
                  <span>多様・広範</span>
                </div>
              </div>
              <button
                onClick={() => handleModeChange(modeId)}
                className="text-xs text-blue-500 hover:underline"
              >
                デフォルトに戻す
              </button>
            </div>
          )}
        </div>
      </div>

      <Card className="mx-6 mb-6 flex flex-col flex-1 overflow-hidden mt-2">
        <CardHeader className="pb-2 shrink-0">
          <CardTitle className="text-sm text-muted-foreground">
            経営者支援AI（LangGraph + Ollama）
          </CardTitle>
        </CardHeader>

        <CardContent className="flex-1 overflow-y-auto space-y-4 pb-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  msg.role === "user" ? "bg-blue-600 text-white" : "bg-muted"
                }`}
              >
                <div className="flex items-center gap-1 flex-wrap mb-1">
                  {msg.route && (
                    <span className={`text-xs px-2 py-0.5 rounded-full ${routeColor[msg.route] || "bg-gray-100 text-gray-800"}`}>
                      {routeLabel[msg.route] || msg.route}
                    </span>
                  )}
                  {msg.latency_ms && (
                    <span className="text-xs text-gray-400">
                      {(msg.latency_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                  {msg.mode && msg.role === "ai" && (
                    <span className="text-xs text-gray-400">
                      [{MODES.find(m => m.id === msg.mode)?.label || msg.mode}]
                    </span>
                  )}
                  {msg.file && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/20">
                      {msg.file}
                    </span>
                  )}
                </div>

                {/* Markdownレンダリング */}
                <div className="text-sm mt-1 prose prose-sm max-w-none
                  prose-headings:font-bold prose-headings:text-gray-800
                  prose-strong:font-bold prose-strong:text-gray-800
                  prose-ul:list-disc prose-ul:pl-4
                  prose-ol:list-decimal prose-ol:pl-4
                  prose-li:my-0.5 prose-p:my-1">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>

                {/* ★ Plotlyインタラクティブグラフ */}
                {msg.graph_json && (
                  <div className="mt-3 rounded-lg overflow-hidden border">
                    <Plot
                      data={JSON.parse(msg.graph_json).data}
                      layout={{
                        ...JSON.parse(msg.graph_json).layout,
                        autosize: true,
                        margin:   { l: 40, r: 20, t: 40, b: 40 },
                      }}
                      config={{
                        displayModeBar:         true,
                        displaylogo:            false,
                        modeBarButtonsToRemove: ["lasso2d", "select2d"],
                        toImageButtonOptions: {
                          format:   "png",
                          filename: "keiei-ai-graph",
                          scale:    2,
                        },
                      }}
                      style={{ width: "100%", height: "400px" }}
                      useResizeHandler
                    />
                  </div>
                )}

                {/* フォールバック：PNG画像 */}
                {!msg.graph_json && msg.graph_base64 && (
                  <img
                    src={`data:image/png;base64,${msg.graph_base64}`}
                    alt="データグラフ"
                    className="mt-3 rounded-lg max-w-full border"
                  />
                )}

                {/* 👍👎 フィードバック */}
                {msg.role === "ai" && msg.session_id && (
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => sendFeedback(i, "good")}
                      disabled={!!msg.feedback}
                      className={`text-xs px-2 py-1 rounded transition-colors ${
                        msg.feedback === "good"
                          ? "bg-green-500 text-white"
                          : "bg-gray-100 hover:bg-green-100 text-gray-600"
                      }`}
                      title="役に立った"
                    >👍</button>
                    <button
                      onClick={() => sendFeedback(i, "bad")}
                      disabled={!!msg.feedback}
                      className={`text-xs px-2 py-1 rounded transition-colors ${
                        msg.feedback === "bad"
                          ? "bg-red-500 text-white"
                          : "bg-gray-100 hover:bg-red-100 text-gray-600"
                      }`}
                      title="改善が必要"
                    >👎</button>
                    {msg.feedback && (
                      <span className="text-xs text-gray-400 self-center">
                        フィードバック送信済み
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-lg px-4 py-2">
                <p className="text-sm text-muted-foreground animate-pulse">
                  {modeId === "reasoning" || modeId === "expert" ? "深く考え中..." : "考え中..."}
                </p>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </CardContent>

        {file && (
          <div className="px-4 py-2 border-t bg-blue-50 flex items-center justify-between shrink-0">
            <span className="text-xs text-blue-700">{file.name}</span>
            <button
              onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = ""; }}
              className="text-xs text-red-500 hover:text-red-700"
            >削除</button>
          </div>
        )}

        {listening && (
          <div className="px-4 py-2 border-t bg-red-50 flex items-center gap-2 shrink-0">
            <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            <span className="text-xs text-red-600">音声認識中...話しかけてください</span>
          </div>
        )}

        <div className="p-4 border-t flex gap-2 shrink-0">
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPT_TYPES}
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />

          <button
            onClick={() => fileRef.current?.click()}
            disabled={loading}
            className="px-3 py-2 border rounded-md text-sm text-gray-500 hover:bg-gray-50 disabled:opacity-50"
            title="ファイルをアップロード"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
            </svg>
          </button>

          <button
            onClick={listening ? stopVoice : startVoice}
            disabled={loading}
            className={`px-3 py-2 border rounded-md text-sm disabled:opacity-50 transition-colors ${
              listening ? "bg-red-500 text-white border-red-500" : "text-gray-500 hover:bg-gray-50"
            }`}
            title={listening ? "録音停止" : "音声入力"}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
            </svg>
          </button>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder={listening ? "音声認識中..." : "質問を入力してください..."}
            className="flex-1 px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <Button onClick={sendMessage} disabled={loading}>
            送信
          </Button>
        </div>
      </Card>
    </div>
  );
}