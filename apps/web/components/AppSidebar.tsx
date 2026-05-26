'use client';

import React from 'react';
import { useAppStore, ViewTab } from '@/lib/store';
import {
  LayoutDashboard,
  ImagePlus,
  Brain,
  ClipboardList,
  Settings,
  Menu,
  X,
  FileText,
  MessageSquare,
  PenTool,
  Monitor,
  Merge,
  Sun,
  Moon,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useTheme } from 'next-themes';

const navItems: { id: ViewTab; label: string; icon: React.ReactNode }[] = [
  { id: 'dashboard', label: 'لوحة التحكم', icon: <LayoutDashboard className="h-5 w-5" /> },
  { id: 'processor', label: 'معالجة الصور', icon: <ImagePlus className="h-5 w-5" /> },
  { id: 'training', label: 'بيانات التدريب', icon: <Brain className="h-5 w-5" /> },
  { id: 'logs', label: 'سجل المعالجة', icon: <ClipboardList className="h-5 w-5" /> },
  { id: 'settings', label: 'الإعدادات', icon: <Settings className="h-5 w-5" /> },
  { id: 'ai-chat', label: 'مساعد الذكاء', icon: <MessageSquare className="h-5 w-5" /> },
  { id: 'handwriting-trainer', label: 'تدريب خط اليد', icon: <PenTool className="h-5 w-5" /> },
  { id: 'project-merge', label: 'دمج المشاريع', icon: <Merge className="h-5 w-5" /> },
  { id: 'desktop-app', label: 'تطبيق سطح المكتب', icon: <Monitor className="h-5 w-5" /> },
  { id: 'mistral', label: 'Mistral AI', icon: <Sparkles className="h-5 w-5" /> },
];

export default function AppSidebar() {
  const { activeTab, setActiveTab, sidebarOpen, setSidebarOpen } = useAppStore();
  const { theme, setTheme } = useTheme();

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile toggle */}
      <button
        className="fixed top-4 right-4 z-50 lg:hidden bg-primary text-primary-foreground p-2 rounded-lg shadow-lg"
        onClick={() => setSidebarOpen(!sidebarOpen)}
      >
        {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed right-0 top-0 h-full bg-sidebar text-sidebar-foreground z-40 transition-transform duration-300 ease-in-out',
          'w-64 flex flex-col shadow-xl',
          'lg:translate-x-0 lg:static lg:z-auto',
          sidebarOpen ? 'translate-x-0' : 'translate-x-full lg:translate-x-0'
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 p-6 border-b border-sidebar-border">
          <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-primary text-primary-foreground">
            <FileText className="h-6 w-6" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-bold text-sidebar-foreground truncate">
              معالج المستندات
            </h1>
            <p className="text-xs text-sidebar-foreground/60">الطبية</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setActiveTab(item.id);
                if (window.innerWidth < 1024) setSidebarOpen(false);
              }}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200',
                activeTab === item.id
                  ? 'bg-primary text-primary-foreground shadow-md shadow-primary/25'
                  : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
              )}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-sidebar-border space-y-2">
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-all"
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            <span>{theme === 'dark' ? 'الوضع الفاتح' : 'الوضع الداكن'}</span>
          </button>
          <div className="text-xs text-sidebar-foreground/40 text-center">
            معالج المستندات الطبية v3.2
          </div>
        </div>
      </aside>
    </>
  );
}
