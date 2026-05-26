'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import {
  Send,
  Trash2,
  Sparkles,
  ScanLine,
  Settings2,
  HelpCircle,
  Loader2,
  MessageSquare,
  ImageIcon,
  CheckCircle2,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';

const quickActions = [
  {
    label: 'تحليل الصورة الحالية',
    icon: <ImageIcon className="h-3.5 w-3.5" />,
    prompt: 'حلل خصائص الصورة الحالية واقترح أفضل إعدادات للمعالجة. الصورة بأبعاد متوسطة مع حدود رمادية حولها.',
  },
  {
    label: 'اقتراح إعدادات مثالية',
    icon: <Sparkles className="h-3.5 w-3.5" />,
    prompt: 'ما هي الإعدادات المثالية لمعالجة صور مستندات طبية؟ أريد أفضل جودة ممكنة مع الحفاظ على المحتوى.',
  },
  {
    label: 'شرح خوارزمية القص',
    icon: <ScanLine className="h-3.5 w-3.5" />,
    prompt: 'اشرح خوارزمية القص الذكية (smart_auto_crop_v2) وكيف تعمل بالتفصيل؟',
  },
  {
    label: 'كيف أصلح مشكلة الميلان؟',
    icon: <HelpCircle className="h-3.5 w-3.5" />,
    prompt: 'كيف أصلح مشكلة الميلان في صور المستندات الطبية؟ ما هي خوارزمية auto_detect_skew_v2 وكيف تعمل؟',
  },
];

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString('ar-EG', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function AIChatView() {
  const {
    chatMessages,
    addChatMessage,
    clearChat,
    isChatLoading,
    setIsChatLoading,
    images,
    selectedImageId,
    settings,
    setSettings,
  } = useAppStore();

  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedImage = images.find((img) => img.id === selectedImageId);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isChatLoading]);

  async function applySettingsToServer(parsedSettings: NonNullable<ReturnType<typeof useAppStore.getState>['settings']>) {
    try {
      // Build the update payload from current settings, overriding with parsed values
      const currentSettings = useAppStore.getState().settings || {};
      const payload = {
        pageThreshold: parsedSettings.pageThreshold ?? currentSettings.pageThreshold ?? 200,
        grayThreshold: parsedSettings.grayThreshold ?? currentSettings.grayThreshold ?? 230,
        padding: parsedSettings.padding ?? currentSettings.padding ?? 10,
        minConfidence: parsedSettings.minConfidence ?? currentSettings.minConfidence ?? 0.85,
        autoSave: currentSettings.autoSave ?? true,
        autoDeskew: currentSettings.autoDeskew ?? true,
        autoCrop: currentSettings.autoCrop ?? true,
      };

      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (data.success) {
        setSettings(data.settings);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  async function sendMessage(content: string) {
    if (!content.trim() || isChatLoading) return;

    addChatMessage({ role: 'user', content: content.trim() });
    setInputValue('');
    setIsChatLoading(true);

    try {
      const res = await fetch('/api/ai-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            ...chatMessages.map((m) => ({ role: m.role, content: m.content })),
            { role: 'user', content: content.trim() },
          ],
          imageContext: selectedImage
            ? {
                name: selectedImage.originalName,
                dimensions: `${selectedImage.width}x${selectedImage.height}`,
                status: selectedImage.status,
                blurBefore: selectedImage.blurBefore,
                blurAfter: selectedImage.blurAfter,
                confidence: selectedImage.confidence,
                operations: selectedImage.operations,
                settings: settings,
              }
            : null,
        }),
      });

      const data = await res.json();
      addChatMessage({
        role: 'assistant',
        content: data.reply,
        parsedSettings: data.parsedSettings || null,
      });

      // Auto-apply settings if found
      if (data.parsedSettings && Object.keys(data.parsedSettings).length > 0) {
        const applied = await applySettingsToServer(data.parsedSettings);
        if (applied) {
          const settingLabels: Record<string, string> = {
            pageThreshold: 'عتبة الصفحة',
            grayThreshold: 'عتبة الرمادي',
            padding: 'الحشوة',
            minConfidence: 'الحد الأدنى للثقة',
          };
          const details = Object.entries(data.parsedSettings)
            .map(([key, val]) => `${settingLabels[key] || key}: ${typeof val === 'number' && key === 'minConfidence' ? `${Math.round(val * 100)}%` : val}`)
            .join('، ');
          toast.success('تم تطبيق اقتراح الذكاء الاصطناعي بنجاح', {
            description: details,
            duration: 5000,
          });
        }
      }
    } catch {
      addChatMessage({
        role: 'assistant',
        content: 'عذراً، حدث خطأ في الاتصال. يرجى المحاولة مرة أخرى.',
      });
    } finally {
      setIsChatLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage(inputValue);
  }

  function handleQuickAction(prompt: string) {
    sendMessage(prompt);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputValue);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-0px)]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 lg:px-6 border-b bg-white">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-emerald-100">
            <MessageSquare className="h-5 w-5 text-emerald-600" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900">مساعد الذكاء الاصطناعي</h2>
            <p className="text-sm text-slate-500">
              مساعدك المتخصص في معالجة المستندات الطبية
            </p>
          </div>
        </div>
        {chatMessages.length > 0 && (
          <Button
            onClick={clearChat}
            variant="outline"
            size="sm"
            className="text-slate-500 hover:text-red-600 hover:border-red-200"
          >
            <Trash2 className="h-4 w-4 ml-2" />
            مسح المحادثة
          </Button>
        )}
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto bg-slate-50 p-4 lg:p-6">
        {chatMessages.length === 0 ? (
          /* Welcome Screen */
          <div className="flex flex-col items-center justify-center h-full max-w-lg mx-auto text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-emerald-200">
                <Sparkles className="h-10 w-10 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-slate-800 mb-2">
                مرحباً بك في المساعد الذكي
              </h3>
              <p className="text-slate-500 mb-8 leading-relaxed">
                أنا مساعدك المتخصص في معالجة صور المستندات الطبية.
                <br />
                يمكنني مساعدتك في ضبط الإعدادات، تحليل الصور، وشرح الخوارزميات.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="w-full space-y-3"
            >
              <p className="text-sm font-medium text-slate-600 mb-3">
                <Settings2 className="h-4 w-4 inline ml-1" />
                إجراءات سريعة
              </p>
              {quickActions.map((action, index) => (
                <motion.button
                  key={action.label}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: 0.3 + index * 0.1 }}
                  onClick={() => handleQuickAction(action.prompt)}
                  className="w-full flex items-center gap-3 p-4 bg-white rounded-xl border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/50 transition-all text-right group"
                >
                  <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-emerald-100 text-emerald-600 group-hover:bg-emerald-200 transition-colors">
                    {action.icon}
                  </div>
                  <span className="text-sm font-medium text-slate-700 group-hover:text-emerald-700 transition-colors">
                    {action.label}
                  </span>
                </motion.button>
              ))}
            </motion.div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-4">
            <AnimatePresence mode="popLayout">
              {chatMessages.map((message, index) => (
                <motion.div
                  key={`${message.timestamp}-${index}`}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className={`flex ${message.role === 'user' ? 'justify-start' : 'justify-end'}`}
                >
                  <div
                    className={`flex items-start gap-3 max-w-[85%] ${
                      message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                    }`}
                  >
                    {/* Avatar */}
                    <div
                      className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${
                        message.role === 'user'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-200 text-slate-600'
                      }`}
                    >
                      {message.role === 'user' ? (
                        <span className="text-xs font-bold">أنت</span>
                      ) : (
                        <Sparkles className="h-4 w-4" />
                      )}
                    </div>

                    {/* Message Bubble */}
                    <div
                      className={`rounded-2xl px-4 py-3 ${
                        message.role === 'user'
                          ? 'bg-emerald-600 text-white rounded-tr-md'
                          : 'bg-white text-slate-800 border border-slate-200 rounded-tl-md shadow-sm'
                      }`}
                    >
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">
                        {message.content}
                      </p>

                      {/* Settings Card */}
                      {message.role === 'assistant' && message.parsedSettings && Object.keys(message.parsedSettings).length > 0 && (
                        <motion.div
                          initial={{ opacity: 0, scale: 0.95 }}
                          animate={{ opacity: 1, scale: 1 }}
                          className="mt-3 p-3 rounded-xl bg-emerald-50 border border-emerald-200"
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                            <span className="text-xs font-bold text-emerald-700">تم تطبيق الإعدادات تلقائياً</span>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {message.parsedSettings.pageThreshold !== undefined && (
                              <span className="inline-flex items-center px-2 py-1 rounded-md bg-white text-xs font-medium text-emerald-700 border border-emerald-100">
                                عتبة الصفحة: {message.parsedSettings.pageThreshold}
                              </span>
                            )}
                            {message.parsedSettings.grayThreshold !== undefined && (
                              <span className="inline-flex items-center px-2 py-1 rounded-md bg-white text-xs font-medium text-emerald-700 border border-emerald-100">
                                عتبة الرمادي: {message.parsedSettings.grayThreshold}
                              </span>
                            )}
                            {message.parsedSettings.padding !== undefined && (
                              <span className="inline-flex items-center px-2 py-1 rounded-md bg-white text-xs font-medium text-emerald-700 border border-emerald-100">
                                الحشوة: {message.parsedSettings.padding}px
                              </span>
                            )}
                            {message.parsedSettings.minConfidence !== undefined && (
                              <span className="inline-flex items-center px-2 py-1 rounded-md bg-white text-xs font-medium text-emerald-700 border border-emerald-100">
                                الثقة: {Math.round(message.parsedSettings.minConfidence * 100)}%
                              </span>
                            )}
                          </div>
                        </motion.div>
                      )}

                      <p
                        className={`text-[10px] mt-1.5 ${
                          message.role === 'user'
                            ? 'text-emerald-200'
                            : 'text-slate-400'
                        }`}
                      >
                        {formatTime(message.timestamp)}
                      </p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Loading Animation */}
            {isChatLoading && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex justify-end"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 h-8 w-8 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-md px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 text-emerald-500 animate-spin" />
                      <span className="text-sm text-slate-500">جارٍ التفكير...</span>
                    </div>
                    <div className="flex gap-1 mt-2">
                      <motion.div
                        className="w-2 h-2 rounded-full bg-emerald-400"
                        animate={{ scale: [1, 1.3, 1] }}
                        transition={{ repeat: Infinity, duration: 0.8, delay: 0 }}
                      />
                      <motion.div
                        className="w-2 h-2 rounded-full bg-emerald-400"
                        animate={{ scale: [1, 1.3, 1] }}
                        transition={{ repeat: Infinity, duration: 0.8, delay: 0.2 }}
                      />
                      <motion.div
                        className="w-2 h-2 rounded-full bg-emerald-400"
                        animate={{ scale: [1, 1.3, 1] }}
                        transition={{ repeat: Infinity, duration: 0.8, delay: 0.4 }}
                      />
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Quick Actions Bar (shown during chat) */}
      {chatMessages.length > 0 && (
        <div className="px-4 lg:px-6 py-2 bg-white border-t">
          <div className="max-w-3xl mx-auto flex gap-2 overflow-x-auto scrollbar-none">
            {quickActions.map((action) => (
              <button
                key={action.label}
                onClick={() => handleQuickAction(action.prompt)}
                disabled={isChatLoading}
                className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 rounded-full hover:bg-emerald-50 hover:text-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {action.icon}
                {action.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 lg:px-6 bg-white border-t">
        <form
          onSubmit={handleSubmit}
          className="max-w-3xl mx-auto flex items-center gap-3"
        >
          <Input
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="اكتب سؤالك هنا..."
            disabled={isChatLoading}
            className="flex-1 h-12 text-sm rounded-xl border-slate-200 focus:border-emerald-400 focus:ring-emerald-100"
          />
          <Button
            type="submit"
            disabled={!inputValue.trim() || isChatLoading}
            className="h-12 w-12 rounded-xl bg-emerald-600 hover:bg-emerald-700 p-0 flex items-center justify-center"
          >
            {isChatLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </Button>
        </form>
        <p className="text-[11px] text-slate-400 text-center mt-2 max-w-3xl mx-auto">
          المساعد الذكي يمكنه اقتراح إعدادات المعالجة تلقائياً بناءً على خصائص صورتك الحالية
        </p>
      </div>
    </div>
  );
}
