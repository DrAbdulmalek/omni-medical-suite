import { create } from 'zustand';

export type ViewTab = 'dashboard' | 'processor' | 'training' | 'logs' | 'settings' | 'ai-chat' | 'handwriting-trainer' | 'project-merge' | 'desktop-app' | 'mistral';

export interface ImageItem {
  id: string;
  fileName: string;
  originalName: string;
  width: number;
  height: number;
  cropLeft: number;
  cropTop: number;
  cropRight: number;
  cropBottom: number;
  deskewAngle: number;
  blurBefore: number;
  blurAfter: number;
  status: string;
  confidence: number;
  operations: string[];
  pageNumber?: string;
  thumbnailUrl?: string;
  previewUrl?: string;
}

export interface LogItem {
  id: string;
  imageName: string;
  action: string;
  details: string;
  quality: number;
  timestamp: string;
}

export interface StatsData {
  totalImages: number;
  processed: number;
  pending: number;
  skipped: number;
  avgBlurBefore: number;
  avgBlurAfter: number;
  avgImprovement: number;
}

export interface TrainingRecordItem {
  id: string;
  imageName: string;
  confidence: number;
  operations: string[];
  blurBefore: number;
  blurAfter: number;
  improvement: number;
  createdAt: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  parsedSettings?: {
    pageThreshold?: number;
    grayThreshold?: number;
    padding?: number;
    minConfidence?: number;
  } | null;
}

export interface ModelStatus {
  trained: boolean;
  lastTrained: string;
  entries: number;
  avgConfidence: number;
}

interface AppState {
  activeTab: ViewTab;
  setActiveTab: (tab: ViewTab) => void;

  chatMessages: ChatMessage[];
  addChatMessage: (msg: { role: 'user' | 'assistant'; content: string; parsedSettings?: ChatMessage['parsedSettings'] }) => void;
  clearChat: () => void;
  isChatLoading: boolean;
  setIsChatLoading: (v: boolean) => void;

  images: ImageItem[];
  setImages: (images: ImageItem[]) => void;
  selectedImageId: string | null;
  setSelectedImageId: (id: string | null) => void;

  isProcessing: boolean;
  setIsProcessing: (v: boolean) => void;

  processingProgress: { current: number; total: number };
  setProcessingProgress: (p: { current: number; total: number }) => void;

  logs: LogItem[];
  setLogs: (logs: LogItem[]) => void;

  stats: StatsData | null;
  setStats: (stats: StatsData) => void;

  sidebarOpen: boolean;
  setSidebarOpen: (v: boolean) => void;

  settings: {
    pageThreshold: number;
    grayThreshold: number;
    autoSave: boolean;
    autoDeskew: boolean;
    autoCrop: boolean;
    padding: number;
    minConfidence: number;
  } | null;
  setSettings: (settings: AppState['settings']) => void;

  modelStatus: ModelStatus | null;
  setModelStatus: (status: ModelStatus | null) => void;

  trainingWordsFilter: string;
  setTrainingWordsFilter: (filter: string) => void;
  selectedWordId: string | null;
  setSelectedWordId: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: 'dashboard',
  setActiveTab: (tab) => set({ activeTab: tab }),

  images: [],
  setImages: (images) => set({ images }),
  selectedImageId: null,
  setSelectedImageId: (id) => set({ selectedImageId: id }),

  isProcessing: false,
  setIsProcessing: (v) => set({ isProcessing: v }),

  processingProgress: { current: 0, total: 0 },
  setProcessingProgress: (p) => set({ processingProgress: p }),

  logs: [],
  setLogs: (logs) => set({ logs }),

  stats: null,
  setStats: (stats) => set({ stats }),

  sidebarOpen: true,
  setSidebarOpen: (v) => set({ sidebarOpen: v }),

  chatMessages: [],
  addChatMessage: (msg) =>
    set((state) => ({
      chatMessages: [
        ...state.chatMessages,
        { ...msg, timestamp: new Date().toISOString() },
      ],
    })),
  clearChat: () => set({ chatMessages: [] }),
  isChatLoading: false,
  setIsChatLoading: (v) => set({ isChatLoading: v }),

  settings: null,
  setSettings: (settings) => set({ settings }),

  modelStatus: null,
  setModelStatus: (status) => set({ modelStatus: status }),

  trainingWordsFilter: 'all',
  setTrainingWordsFilter: (filter) => set({ trainingWordsFilter: filter }),
  selectedWordId: null,
  setSelectedWordId: (id) => set({ selectedWordId: id }),
}));
