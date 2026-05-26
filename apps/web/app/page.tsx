'use client';

import React, { useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import AppSidebar from '@/components/AppSidebar';
import DashboardView from '@/components/DashboardView';
import ImageProcessorView from '@/components/ImageProcessorView';
import TrainingDataView from '@/components/TrainingDataView';
import ProcessingLogView from '@/components/ProcessingLogView';
import SettingsPanel from '@/components/SettingsPanel';
import AIChatView from '@/components/AIChatView';
import HandwritingTrainerView from '@/components/HandwritingTrainerView';
import DesktopAppView from '@/components/DesktopAppView';
import ProjectMergeView from '@/components/ProjectMergeView';
import MistralIntegrationView from '@/components/MistralIntegrationView';

export default function Home() {
  const { activeTab } = useAppStore();

  // Auto-import data on first load
  useEffect(() => {
    async function initData() {
      try {
        await fetch('/api/init-data', { method: 'POST' });
      } catch {
        // Silent fail - data may already be imported
      }
    }
    initData();
  }, []);

  return (
    <div className="flex h-screen overflow-hidden" dir="rtl">
      <AppSidebar />
      <main className="flex-1 overflow-hidden bg-slate-50">
        {activeTab === 'dashboard' && <DashboardView />}
        {activeTab === 'processor' && <ImageProcessorView />}
        {activeTab === 'training' && <TrainingDataView />}
        {activeTab === 'logs' && <ProcessingLogView />}
        {activeTab === 'settings' && <SettingsPanel />}
        {activeTab === 'ai-chat' && <AIChatView />}
        {activeTab === 'handwriting-trainer' && <HandwritingTrainerView />}
        {activeTab === 'project-merge' && <ProjectMergeView />}
        {activeTab === 'desktop-app' && <DesktopAppView />}
        {activeTab === 'mistral' && <MistralIntegrationView />}
      </main>
    </div>
  );
}
