'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowUpRight,
  HeartHandshake,
  Check,
  MessageCircleMore,
  RotateCcw,
  SendHorizontal,
  ShoppingBag,
  Sparkles,
} from 'lucide-react';

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';

type ProductCode = 'starter' | 'standard' | 'pro' | 'agency';
type Product = {
  code: ProductCode;
  name: string;
  price: string;
  credits: string;
  description: string;
  target_user: string;
  features: string[];
  purchase_url: string;
};
type Message = {
  id: string;
  role: 'assistant' | 'user';
  content: string;
  time: string;
  product?: Product | null;
};
type Signals = { emotion: string; stage: string; need: string };
type ChatResponse = {
  session_id: string;
  message_id: string;
  reply: string;
  signals: Signals;
  product: Product | null;
};
type HistoryMessage = {
  id: string;
  role: 'assistant' | 'user';
  content: string;
  created_at: string;
  product?: Product | null;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (
  typeof window === 'undefined'
    ? 'http://localhost:8000'
    : `${window.location.protocol}//${window.location.hostname}:8000`
);
const initialSignals: Signals = { emotion: '等待交流', stage: '尚未了解', need: '等待交流' };
const productSummary: Record<ProductCode, { name: string; price: string; credits: string }> = {
  starter: { name: 'Starter', price: '$29', credits: '300 Credits' },
  standard: { name: 'Standard', price: '$99', credits: '1,000 Credits' },
  pro: { name: 'Pro', price: '$199', credits: '2,000 Credits' },
  agency: { name: 'Agency', price: 'Custom', credits: '按方案配置' },
};
const welcomeMessage: Message = {
  id: 'welcome',
  role: 'assistant',
  content: '嗨，我是 Nola。你可以跟我聊聊最近的创作状态，也可以问我 Onely 的功能、套餐或创作者运营问题。',
  time: '现在',
};

function formatTime(value?: string) {
  const date = value ? new Date(value) : new Date();
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }).format(date);
}

function PlanCard({ product }: { product: Product }) {
  return (
    <Card className="mt-3 max-w-[430px] overflow-hidden border-0 bg-white shadow-[0_16px_48px_rgba(54,35,74,0.11)] ring-1 ring-[#dfd3e7]">
      <div className="h-1.5 bg-gradient-to-r from-[#ef8f67] to-[#8f65d6]" />
      <CardHeader className="grid grid-cols-[1fr_auto] items-start gap-3 pb-0">
        <div>
          <div className="mb-1.5 flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#80618f]">Nola 推荐</span>
            <Badge className="h-5 bg-[#f1e9f5] px-2 text-[#684478]">Onely</Badge>
          </div>
          <h3 className="text-xl font-semibold tracking-[-0.02em] text-[#2c2130]">{product.name}</h3>
        </div>
        <div className="text-right">
          <div className="text-xl font-semibold text-[#2c2130]">{product.price}</div>
          <div className="text-xs text-[#8a788f]">{product.credits}</div>
        </div>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm leading-6 text-[#695c6e]">{product.description}</p>
        <div className="flex flex-wrap gap-2">
          {product.features.map((feature) => (
            <span key={feature} className="inline-flex items-center gap-1 rounded-full bg-[#f8f4f9] px-2.5 py-1 text-xs text-[#604b69]">
              <Check className="size-3 text-[#8e62a2]" />{feature}
            </span>
          ))}
        </div>
      </CardContent>
      <CardFooter className="justify-between border-[#eee7f0] bg-[#fcfafc]">
        <span className="text-xs text-[#8a788f]">公开信息 · Private Beta</span>
        <Button size="sm" nativeButton={false} className="rounded-full bg-[#6f4b7d] px-3.5 text-white hover:bg-[#5c3d69]" render={<a href={product.purchase_url} target="_blank" rel="noreferrer" />}>
          申请体验<ArrowUpRight />
        </Button>
      </CardFooter>
    </Card>
  );
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([welcomeMessage]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const [signals, setSignals] = useState<Signals>(initialSignals);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const existing = window.localStorage.getItem('nola-demo-session-id');
    const id = existing ?? crypto.randomUUID();
    window.localStorage.setItem('nola-demo-session-id', id);
    setSessionId(id);
    fetch(`${API_BASE}/api/sessions/${id}/messages`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('history')))
      .then((history: HistoryMessage[]) => {
        if (history.length) {
          setMessages(history.map((item) => ({ ...item, time: formatTime(item.created_at) })));
          const lastAssistant = [...history].reverse().find((item) => item.role === 'assistant');
          if (lastAssistant) setSignals({ emotion: '已恢复会话', stage: '继续交流', need: '查看历史消息' });
        }
      })
      .catch(() => setError('暂时无法连接后端，请确认 FastAPI 已启动。'));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages, thinking]);

  const latestPlan = useMemo(
    () => [...messages].reverse().find((message) => message.product)?.product?.code,
    [messages],
  );

  const sendMessage = async (preset?: string) => {
    const text = (preset ?? input).trim();
    if (!text || thinking || !sessionId) return;
    const userMessage: Message = { id: crypto.randomUUID(), role: 'user', content: text, time: formatTime() };
    setMessages((current) => [...current, userMessage]);
    setInput('');
    setError('');
    setThinking(true);
    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? '请求失败');
      const result = payload as ChatResponse;
      setSignals(result.signals);
      setMessages((current) => [...current, {
        id: result.message_id,
        role: 'assistant',
        content: result.reply,
        product: result.product,
        time: formatTime(),
      }]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '暂时无法回复，请重试。');
    } finally {
      setThinking(false);
    }
  };

  const resetChat = async () => {
    if (sessionId) {
      try { await fetch(`${API_BASE}/api/sessions/${sessionId}`, { method: 'DELETE' }); } catch { /* keep UI reset available */ }
    }
    const nextId = crypto.randomUUID();
    window.localStorage.setItem('nola-demo-session-id', nextId);
    setSessionId(nextId);
    setMessages([welcomeMessage]);
    setSignals(initialSignals);
    setError('');
    setInput('');
  };

  return (
    <main className="h-screen min-w-[1180px] overflow-hidden bg-[#f6f2f2] text-[#2c2130]">
      <header className="flex h-[68px] items-center justify-between border-b border-[#e7dfe8] bg-[#fbf9f8]/95 px-7 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="grid size-9 place-items-center rounded-xl bg-[#6f4b7d] text-white shadow-sm"><Sparkles className="size-4" /></div>
          <div><h1 className="text-sm font-semibold tracking-[-0.01em]">Nola · Onely 智能顾问</h1><p className="text-xs text-[#8a788f]">DeepSeek 驱动的聊天、情感陪伴与智能推荐</p></div>
        </div>
        <Button variant="ghost" size="sm" onClick={resetChat} className="rounded-full text-[#755d7d] hover:bg-[#eee6f0]" aria-label="重新开始对话"><RotateCcw /><span>重新开始</span></Button>
      </header>

      <div className="mx-auto grid h-[calc(100vh-68px)] max-w-[1500px] grid-cols-[250px_minmax(0,1fr)_288px]">
        <aside className="flex flex-col border-r border-[#e7dfe8] bg-[#f2ecef] p-5">
          <div className="rounded-[26px] bg-[#fbf8f8] p-4 shadow-[0_14px_40px_rgba(56,39,62,0.07)] ring-1 ring-[#e6dce7]">
            <div className="relative overflow-hidden rounded-[22px] bg-gradient-to-b from-[#d9c8e5] to-[#f2ddd1] p-2">
              <img src="/nola-avatar.png" alt="虚拟达人 Nola 头像" className="aspect-square w-full rounded-[18px] object-cover" />
              <div className="absolute bottom-4 left-4 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-medium text-[#594461] shadow-sm backdrop-blur">在线陪你聊</div>
            </div>
            <div className="px-1 pb-1 pt-4">
              <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Nola</h2><Badge className="bg-[#efe5f2] text-[#714f7e]">AI 顾问</Badge></div>
              <p className="mt-1 text-sm leading-5 text-[#7d6d81]">懂创作者情绪，也能结合公开资料回答 Onely 问题。</p>
            </div>
          </div>
          <div className="mt-5 space-y-2.5 px-1">
            <div className="flex items-center gap-3 rounded-xl bg-white/60 px-3 py-2.5 text-sm text-[#66566b]"><MessageCircleMore className="size-4 text-[#8a61a0]" />DeepSeek 多轮问答</div>
            <div className="flex items-center gap-3 rounded-xl bg-white/60 px-3 py-2.5 text-sm text-[#66566b]"><HeartHandshake className="size-4 text-[#c16d84]" />理解当前情绪</div>
            <div className="flex items-center gap-3 rounded-xl bg-white/60 px-3 py-2.5 text-sm text-[#66566b]"><ShoppingBag className="size-4 text-[#c78658]" />匹配 Onely 套餐</div>
          </div>
        </aside>

        <section className="flex min-h-0 min-w-0 flex-col bg-[#fbf9f8]">
          <div className="border-b border-[#eee7ed] px-7 py-3"><div className="mx-auto max-w-3xl"><p className="text-sm font-medium">和 Nola 聊聊</p><p className="text-xs text-[#938497]">问产品、聊创作状态，或让她帮你比较套餐</p></div></div>
          <div className="flex-1 overflow-y-auto px-7 py-6">
            <div className="mx-auto max-w-3xl space-y-6">
              {messages.map((message) => (
                <div key={message.id} className={`flex items-end gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {message.role === 'assistant' && <Avatar className="mb-1 flex"><AvatarImage src="/nola-avatar.png" alt="Nola" /><AvatarFallback>N</AvatarFallback></Avatar>}
                  <div className={`max-w-[78%] ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div className={message.role === 'user' ? 'rounded-[22px] rounded-br-md bg-[#6f4b7d] px-4 py-3 text-[15px] leading-6 text-white shadow-sm' : 'whitespace-pre-wrap rounded-[22px] rounded-bl-md bg-[#f1eaef] px-4 py-3 text-[15px] leading-6 text-[#493b4e] ring-1 ring-[#e9dee8]'}>{message.content}</div>
                    {message.product && <PlanCard product={message.product} />}
                    <p className={`mt-1.5 px-1 text-[10px] text-[#a496a7] ${message.role === 'user' ? 'text-right' : 'text-left'}`}>{message.time}</p>
                  </div>
                </div>
              ))}
              {thinking && <div className="flex items-end gap-3"><Avatar className="mb-1 flex"><AvatarImage src="/nola-avatar.png" alt="Nola" /><AvatarFallback>N</AvatarFallback></Avatar><div className="flex h-11 items-center gap-1.5 rounded-[20px] rounded-bl-md bg-[#f1eaef] px-4 ring-1 ring-[#e9dee8]">{[0, 1, 2].map((dot) => <span key={dot} className="size-1.5 animate-bounce rounded-full bg-[#92799a]" style={{ animationDelay: `${dot * 120}ms` }} />)}</div></div>}
              <div ref={bottomRef} />
            </div>
          </div>
          <div className="border-t border-[#eee7ed] bg-[#fbf9f8]/95 px-7 pb-5 pt-3 backdrop-blur">
            <div className="mx-auto max-w-3xl">
              {error && <div role="alert" className="mb-2 rounded-xl bg-[#fff1f1] px-3 py-2 text-xs text-[#a33f4d]">{error}</div>}
              <div className="mb-2 flex flex-wrap gap-2">
                {['我最近做内容有点焦虑，感觉忙不过来', '我们是小团队，需要每天高频更新', '我刚开始做内容，预算不高'].map((item) => <button key={item} type="button" onClick={() => sendMessage(item)} disabled={thinking} className="rounded-full border border-[#e1d6e3] bg-white px-3 py-1.5 text-xs text-[#755d7d] hover:bg-[#f5eef6] disabled:opacity-50">{item}</button>)}
              </div>
              <div className="flex items-end gap-2 rounded-[22px] border border-[#dcd1de] bg-white p-2 shadow-[0_10px_28px_rgba(50,32,56,0.08)] focus-within:border-[#a486ad] focus-within:ring-3 focus-within:ring-[#b59abc]/20">
                <Textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); } }} placeholder="告诉 Nola 你最近在做什么……" rows={1} className="max-h-28 min-h-11 resize-none border-0 bg-transparent px-3 py-2.5 text-[15px] leading-6 shadow-none focus-visible:ring-0" aria-label="聊天消息" />
                <Button size="icon-lg" onClick={() => sendMessage()} disabled={!input.trim() || thinking || !sessionId} className="rounded-full bg-[#6f4b7d] text-white shadow-sm hover:bg-[#5c3d69]" aria-label="发送消息"><SendHorizontal className="size-4" /></Button>
              </div>
              <p className="mt-2 text-center text-[10px] text-[#a293a5]">Enter 发送 · Shift + Enter 换行 · 回答由 AI 生成，请核对重要信息</p>
            </div>
          </div>
        </section>

        <aside className="block border-l border-[#e7dfe8] bg-[#f8f4f5] p-5">
          <div className="mb-5 flex items-center justify-between"><div><p className="text-sm font-semibold">本轮理解</p><p className="mt-0.5 text-xs text-[#958698]">随对话实时变化</p></div><div className="grid size-8 place-items-center rounded-xl bg-[#eee4f0] text-[#765384]"><HeartHandshake className="size-4" /></div></div>
          <div className="space-y-2.5">{[['情绪', signals.emotion], ['阶段', signals.stage], ['当前需求', signals.need]].map(([label, value]) => <div key={label} className="rounded-xl border border-[#e6dce7] bg-white/75 px-3.5 py-3"><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#9a8a9e]">{label}</p><p className="mt-1 text-sm font-medium text-[#514156]">{value}</p></div>)}</div>
          <div className="my-5 h-px bg-[#e5dce6]" />
          <div className="mb-3 flex items-center justify-between"><p className="text-sm font-semibold">Onely 套餐</p><ShoppingBag className="size-4 text-[#9a789d]" /></div>
          <div className="space-y-2">{(Object.entries(productSummary) as [ProductCode, (typeof productSummary)[ProductCode]][]).map(([code, product]) => <div key={code} className={`flex items-center justify-between rounded-xl border px-3 py-2.5 transition-colors ${latestPlan === code ? 'border-[#a982b2] bg-[#f1e7f3]' : 'border-transparent bg-white/60'}`}><div><p className="text-sm font-medium text-[#514156]">{product.name}</p><p className="text-[11px] text-[#968699]">{product.credits}</p></div><span className="text-sm font-semibold text-[#6f4b7d]">{product.price}</span></div>)}</div>
          <div className="mt-5 rounded-2xl bg-[#34293a] p-4 text-white shadow-lg shadow-[#3a2c41]/10"><div className="mb-2 flex items-center gap-2 text-xs font-semibold text-[#e7d5eb]"><Sparkles className="size-3.5" />MVP 演示提示</div><p className="text-xs leading-5 text-[#d4c7d7]">试试“小团队高频更新”或“刚开始且预算不高”，查看不同的套餐卡片。</p></div>
        </aside>
      </div>
    </main>
  );
}
