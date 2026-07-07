'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import {
  GitBranch,
  Monitor,
  Smartphone,
  Globe,
  CheckCircle2,
  Clock,
  ArrowLeftRight,
  Layers,
  ImageIcon,
  Brain,
  Cpu,
  Database,
  ChevronLeft,
  ExternalLink,
  Github,
  FolderTree,
  Settings,
  Zap,
  Eye,
  Pencil,
  Boxes,
  FileCode,
  Webhook,
} from 'lucide-react';

const projects = [
  {
    id: 'medical-doc-processor',
    name: 'medical-doc-processor',
    nameAr: 'معالج المستندات الطبية',
    description: 'التطبيق الرئيسي - ويب + سطح المكتب',
    type: 'web + desktop',
    tech: ['Next.js', 'Electron', 'Python', 'Sharp', 'Tesseract'],
    status: 'active' as const,
    icon: <Globe className="h-6 w-6" />,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    badgeBg: 'bg-emerald-100 text-emerald-700',
    github: 'https://github.com/DrAbdulmalek/medical-doc-processor',
  },
  {
    id: 'medical-document-scanner',
    name: 'medical-document-scanner',
    nameAr: 'ماسح المستندات الطبية',
    description: 'تطبيق سطح المكتب - PyQt5',
    type: 'desktop (PyQt5)',
    tech: ['Python', 'PyQt5', 'OpenCV', 'NumPy'],
    status: 'merged' as const,
    icon: <Monitor className="h-6 w-6" />,
    color: 'text-teal-600',
    bg: 'bg-teal-50',
    borderColor: 'border-teal-200',
    badgeBg: 'bg-teal-100 text-teal-700',
    note: 'يتم دمج ميزات المسح والتعرف على النصوص',
  },
  {
    id: 'medical-doc-webapp',
    name: 'medical-doc-webapp',
    nameAr: 'تطبيق الويب الطبي',
    description: 'تطبيق ويب - تصميم موبايل أولاً',
    type: 'web (mobile-first)',
    tech: ['React', 'Node.js', 'Express', 'MongoDB'],
    status: 'merged' as const,
    icon: <Smartphone className="h-6 w-6" />,
    color: 'text-cyan-600',
    bg: 'bg-cyan-50',
    borderColor: 'border-cyan-200',
    badgeBg: 'bg-cyan-100 text-cyan-700',
    note: 'يتم دمج واجهة المستخدم المحسنة',
  },
];

const features = [
  {
    title: 'معالجة الصور',
    titleEn: 'Image Processing',
    icon: <ImageIcon className="h-6 w-6" />,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    items: ['Sharp - معالجة متقدمة', 'Smart Crop - قص ذكي', 'Deskew - تصحيح الميلان', 'Gray Border Removal - إزالة الحدود الرمادية'],
    sources: ['medical-doc-processor', 'medical-document-scanner'],
  },
  {
    title: 'تدريب خط اليد',
    titleEn: 'Handwriting Training',
    icon: <Pencil className="h-6 w-6" />,
    color: 'text-teal-600',
    bg: 'bg-teal-50',
    borderColor: 'border-teal-200',
    items: ['OCR - التعرف على النصوص', 'Word Segmentation - تجزئة الكلمات', 'Correction - التصحيح التلقائي', 'Training Interface - واجهة التدريب'],
    sources: ['medical-doc-processor', 'medical-document-scanner'],
  },
  {
    title: 'الذكاء الاصطناعي',
    titleEn: 'AI Capabilities',
    icon: <Brain className="h-6 w-6" />,
    color: 'text-purple-600',
    bg: 'bg-purple-50',
    borderColor: 'border-purple-200',
    items: ['Auto-suggestions - اقتراحات تلقائية', 'Quality Assessment - تقييم الجودة', 'Smart Settings - إعدادات ذكية', 'Chat Assistant - مساعد محادثة'],
    sources: ['medical-doc-processor', 'medical-doc-webapp'],
  },
  {
    title: 'KNN التعلّم',
    titleEn: 'KNN Learning',
    icon: <Cpu className="h-6 w-6" />,
    color: 'text-amber-600',
    bg: 'bg-amber-50',
    borderColor: 'border-amber-200',
    items: ['Training Data - بيانات التدريب', 'Prediction - التنبؤ والتصنيف', 'Model Management - إدارة النماذج', 'Performance Metrics - مقاييس الأداء'],
    sources: ['medical-doc-processor', 'medical-document-scanner'],
  },
];

const mergePhases = [
  {
    phase: 1,
    title: 'التخطيط والتحليل',
    titleEn: 'Planning & Analysis',
    status: 'completed' as const,
    progress: 100,
    description: 'تحليل المشاريع المصدرية وتحديد الميزات المراد دمجها',
  },
  {
    phase: 2,
    title: 'هيكلة المستودع',
    titleEn: 'Repository Structure',
    status: 'completed' as const,
    progress: 100,
    description: 'إنشاء هيكل monorepo مع مشاريع منفصلة',
  },
  {
    phase: 3,
    title: 'دمج الواجهات',
    titleEn: 'UI Integration',
    status: 'completed' as const,
    progress: 100,
    description: 'دمج مكونات واجهة المستخدم من جميع المشاريع',
  },
  {
    phase: 4,
    title: 'دمج الخدمات',
    titleEn: 'Services Integration',
    status: 'completed' as const,
    progress: 100,
    description: 'توحيد APIs وخدمات المعالجة الخلفية',
  },
  {
    phase: 5,
    title: 'تحسين الأداء',
    titleEn: 'Performance Optimization',
    status: 'in-progress' as const,
    progress: 65,
    description: 'تحسين سرعة المعالجة وتقليل استهلاك الموارد',
  },
  {
    phase: 6,
    title: 'الاختبار والتوثيق',
    titleEn: 'Testing & Documentation',
    status: 'pending' as const,
    progress: 30,
    description: 'كتابة الاختبارات والتوثيق الشامل',
  },
  {
    phase: 7,
    title: 'الإطلاق والنشر',
    titleEn: 'Release & Deploy',
    status: 'pending' as const,
    progress: 0,
    description: 'النشر النهائي والتوزيع',
  },
];

const monorepoStructure = [
  {
    name: 'packages/web',
    nameAr: 'تطبيق الويب',
    icon: <Webhook className="h-4 w-4" />,
    color: 'text-emerald-600',
    description: 'Next.js 16 + TypeScript',
  },
  {
    name: 'packages/desktop',
    nameAr: 'سطح المكتب',
    icon: <Monitor className="h-4 w-4" />,
    color: 'text-teal-600',
    description: 'Electron + Python Core',
  },
  {
    name: 'packages/core',
    nameAr: 'المكتبة الأساسية',
    icon: <FileCode className="h-4 w-4" />,
    color: 'text-purple-600',
    description: 'Shared Processing Engine',
  },
  {
    name: 'packages/mobile',
    nameAr: 'تطبيق الموبايل',
    icon: <Smartphone className="h-4 w-4" />,
    color: 'text-cyan-600',
    description: 'React Native',
  },
  {
    name: 'packages/shared',
    nameAr: 'المكتبات المشتركة',
    icon: <Boxes className="h-4 w-4" />,
    color: 'text-amber-600',
    description: 'Types, Utils, Components',
  },
];

function getStatusIcon(status: string) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
    case 'in-progress':
      return <Clock className="h-5 w-5 text-amber-500" />;
    default:
      return <Clock className="h-5 w-5 text-slate-400" />;
  }
}

function getStatusBadge(status: 'completed' | 'in-progress' | 'pending') {
  switch (status) {
    case 'completed':
      return <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 border-0">مكتمل</Badge>;
    case 'in-progress':
      return <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100 border-0">قيد التنفيذ</Badge>;
    default:
      return <Badge className="bg-slate-100 text-slate-500 hover:bg-slate-100 border-0">قيد الانتظار</Badge>;
  }
}

export default function ProjectMergeView() {
  const completedPhases = mergePhases.filter(p => p.status === 'completed').length;
  const overallProgress = Math.round(
    mergePhases.reduce((acc, p) => acc + p.progress, 0) / mergePhases.length
  );

  return (
    <div className="space-y-6 p-4 lg:p-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-xl bg-emerald-50">
              <GitBranch className="h-6 w-6 text-emerald-600" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900">خطة دمج المشاريع</h2>
          </div>
          <p className="text-slate-500 mr-11">
            دمج ثلاثة مشاريع في مستودع موحّد تحت مظلّة medical-doc-suite
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => window.open('https://github.com/DrAbdulmalek/medical-doc-processor', '_blank')}
          >
            <Github className="h-4 w-4" />
            GitHub
          </Button>
          <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 border-0 text-sm px-3 py-1">
            v3.0
          </Badge>
        </div>
      </div>

      {/* Overall Progress */}
      <Card className="border-0 shadow-sm">
        <CardContent className="p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <Zap className="h-5 w-5 text-emerald-600" />
              <span className="font-semibold text-slate-900">التقدم الإجمالي للدمج</span>
            </div>
            <span className="text-sm font-bold text-emerald-600">{overallProgress}%</span>
          </div>
          <Progress value={overallProgress} className="h-3" />
          <p className="text-xs text-slate-400 mt-2">
            {completedPhases} من {mergePhases.length} مراحل مكتملة
          </p>
        </CardContent>
      </Card>

      {/* Project Cards */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Layers className="h-5 w-5 text-slate-600" />
          <h3 className="text-lg font-bold text-slate-900">المشاريع المصدرية</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {projects.map((project) => (
            <Card
              key={project.id}
              className={`border ${project.borderColor} hover:shadow-md transition-all duration-200`}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className={`p-2.5 rounded-xl ${project.bg}`}>
                    <div className={project.color}>{project.icon}</div>
                  </div>
                  {getStatusBadge(project.status)}
                </div>
                <CardTitle className="text-base mt-3">{project.nameAr}</CardTitle>
                <CardDescription className="text-xs font-mono">{project.name}</CardDescription>
              </CardHeader>
              <CardContent className="pt-0 space-y-3">
                <p className="text-sm text-slate-600">{project.description}</p>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">{project.type}</Badge>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {project.tech.map((t) => (
                    <Badge key={t} variant="outline" className="text-xs font-normal">
                      {t}
                    </Badge>
                  ))}
                </div>
                {project.note && (
                  <div className="bg-slate-50 rounded-lg p-2.5 text-xs text-slate-500 flex items-start gap-2">
                    <ArrowLeftRight className="h-4 w-4 text-slate-400 shrink-0 mt-0.5" />
                    <span>{project.note}</span>
                  </div>
                )}
                {project.github && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full gap-2 text-xs"
                    onClick={() => window.open(project.github, '_blank')}
                  >
                    <ExternalLink className="h-3 w-3" />
                    عرض على GitHub
                    <ChevronLeft className="h-3 w-3" />
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Unified Features */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Eye className="h-5 w-5 text-slate-600" />
          <h3 className="text-lg font-bold text-slate-900">الميزات الموحّدة</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {features.map((feature) => (
            <Card key={feature.titleEn} className={`border ${feature.borderColor} hover:shadow-md transition-all duration-200`}>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-xl ${feature.bg}`}>
                    <div className={feature.color}>{feature.icon}</div>
                  </div>
                  <div>
                    <CardTitle className="text-base">{feature.title}</CardTitle>
                    <CardDescription>{feature.titleEn}</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2">
                  {feature.items.map((item) => (
                    <div key={item} className="flex items-center gap-2 text-sm text-slate-600">
                      <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t border-slate-100">
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <span>المصادر:</span>
                    {feature.sources.map((src) => (
                      <Badge key={src} variant="secondary" className="text-xs font-normal">
                        {src}
                      </Badge>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Merge Phases Tracker */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Settings className="h-5 w-5 text-slate-600" />
          <h3 className="text-lg font-bold text-slate-900">مراحل الدمج</h3>
        </div>
        <div className="space-y-3">
          {mergePhases.map((phase) => (
            <Card key={phase.phase} className="border-0 shadow-sm hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  <div className="flex flex-col items-center gap-1 mt-0.5">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${
                        phase.status === 'completed'
                          ? 'bg-emerald-100 text-emerald-700'
                          : phase.status === 'in-progress'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-slate-100 text-slate-500'
                      }`}
                    >
                      {phase.status === 'completed' ? (
                        <CheckCircle2 className="h-5 w-5" />
                      ) : (
                        phase.phase
                      )}
                    </div>
                    {phase.phase < mergePhases.length && (
                      <div
                        className={`w-0.5 h-4 ${
                          phase.status === 'completed' ? 'bg-emerald-300' : 'bg-slate-200'
                        }`}
                      />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <div>
                        <h4 className="font-semibold text-slate-900 text-sm">{phase.title}</h4>
                        <p className="text-xs text-slate-400">{phase.titleEn}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {getStatusBadge(phase.status)}
                        <span className="text-xs font-medium text-slate-500">{phase.progress}%</span>
                      </div>
                    </div>
                    <p className="text-xs text-slate-500 mb-2">{phase.description}</p>
                    <Progress value={phase.progress} className="h-1.5" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Architecture Diagram */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <FolderTree className="h-5 w-5 text-slate-600" />
          <h3 className="text-lg font-bold text-slate-900">هيكل المستودع الموحّد</h3>
        </div>
        <Card className="border-0 shadow-sm">
          <CardContent className="p-6">
            {/* Monorepo Visual Structure */}
            <div className="bg-slate-900 rounded-xl p-6 font-mono text-sm overflow-x-auto">
              <div className="text-emerald-400 mb-4">
                <span className="text-slate-500">$</span> medical-doc-suite/
              </div>
              <div className="space-y-1.5 mr-4">
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">├──</span>
                  <span className="text-amber-400">📦</span>
                  <span className="text-slate-300">packages/</span>
                </div>
                <div className="space-y-1.5 mr-8">
                  {monorepoStructure.map((pkg, idx) => (
                    <div key={pkg.name} className="flex items-center gap-2">
                      <span className="text-slate-500">
                        {idx === monorepoStructure.length - 1 ? '└──' : '├──'}
                      </span>
                      <span className={pkg.color}>●</span>
                      <span className="text-slate-300">{pkg.name}</span>
                      <span className="text-slate-600">—</span>
                      <span className="text-slate-500 text-xs">{pkg.description}</span>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-2 mt-3">
                  <span className="text-slate-500">├──</span>
                  <span className="text-slate-400">📄</span>
                  <span className="text-slate-300">turbo.json</span>
                  <span className="text-slate-600">—</span>
                  <span className="text-slate-500 text-xs">Turborepo Config</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">├──</span>
                  <span className="text-slate-400">📄</span>
                  <span className="text-slate-300">pnpm-workspace.yaml</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">└──</span>
                  <span className="text-slate-400">📄</span>
                  <span className="text-slate-300">README.md</span>
                </div>
              </div>
            </div>

            {/* Package Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mt-4">
              {monorepoStructure.map((pkg) => (
                <div
                  key={pkg.name}
                  className="flex items-center gap-2.5 p-3 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
                >
                  <div className={pkg.color}>{pkg.icon}</div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-700 truncate">{pkg.name}</p>
                    <p className="text-xs text-slate-400 truncate">{pkg.nameAr}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
