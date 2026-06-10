/**
 * mobile/android/screens/HomeScreen.tsx
 * ========================================
 * لوحة التحكم الرئيسية
 * - إحصائيات يومية مع رسم بياني أسبوعي
 * - آخر المستندات مع فلترة سريعة
 * - pull-to-refresh
 * - مؤشر الاتصال بالخادم
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, RefreshControl,
  Dimensions, Animated,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useDocumentsStore, useAuthStore } from '../store';
import { StatsService, DocumentService } from '../services/api';
import type { DailyStats } from '../services/api';
import type { Document } from '../store';

const { width: W } = Dimensions.get('window');
const COLORS = {
  primary: '#1B4F72', secondary: '#2E86C1',
  accent: '#27AE60', warning: '#E67E22',
  danger: '#E74C3C', bg: '#F4F6F7',
  surface: '#FFFFFF', text: '#1A252F',
  textLight: '#5D6D7E', border: '#D5D8DC',
};

// ─── Mini Bar Chart ───────────────────────────────────────────

function WeeklyChart({ data }: { data: number[] }) {
  const max = Math.max(...data, 1);
  const days = ['أحد', 'اثن', 'ثلا', 'أرب', 'خمس', 'جمع', 'سبت'];
  const today = new Date().getDay();

  return (
    <View style={chart.container}>
      <Text style={chart.title}>المعالَجة هذا الأسبوع</Text>
      <View style={chart.bars}>
        {data.map((v, i) => {
          const height = Math.max((v / max) * 80, 4);
          const isToday = i === today;
          return (
            <View key={i} style={chart.barCol}>
              <Text style={chart.barVal}>{v > 0 ? v : ''}</Text>
              <View style={[
                chart.bar,
                { height, backgroundColor: isToday ? COLORS.secondary : COLORS.border },
              ]} />
              <Text style={[chart.dayLabel, isToday && { color: COLORS.secondary, fontWeight: '700' }]}>
                {days[i]}
              </Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}

const chart = StyleSheet.create({
  container: {
    backgroundColor: COLORS.surface, borderRadius: 12,
    padding: 14, marginBottom: 14, elevation: 1,
  },
  title: { fontSize: 13, fontWeight: '600', color: COLORS.textLight, textAlign: 'right', marginBottom: 10 },
  bars: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-around', height: 100 },
  barCol: { alignItems: 'center', gap: 4, flex: 1 },
  barVal: { fontSize: 10, color: COLORS.textLight },
  bar: { width: 24, borderRadius: 4 },
  dayLabel: { fontSize: 10, color: COLORS.textLight },
});

// ─── Stat Card ────────────────────────────────────────────────

function StatCard({
  icon, label, value, color, sub,
}: { icon: string; label: string; value: string | number; color: string; sub?: string }) {
  const anim = React.useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.spring(anim, { toValue: 1, useNativeDriver: true, friction: 5 }).start();
  }, []);

  return (
    <Animated.View style={[styles.statCard, { borderTopColor: color, transform: [{ scale: anim }] }]}>
      <Text style={styles.statIcon}>{icon}</Text>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
      {sub && <Text style={styles.statSub}>{sub}</Text>}
    </Animated.View>
  );
}

// ─── Status Badge ─────────────────────────────────────────────

const STATUS_MAP: Record<string, { color: string; bg: string; label: string }> = {
  completed:  { color: COLORS.accent,   bg: '#D5F5E3', label: '✅ مكتمل'   },
  review:     { color: COLORS.warning,  bg: '#FDEBD0', label: '🔍 مراجعة'  },
  processing: { color: COLORS.secondary,bg: '#D6EAF8', label: '⏳ جارٍ'    },
  failed:     { color: COLORS.danger,   bg: '#FADBD8', label: '❌ فشل'     },
  pending:    { color: COLORS.textLight, bg: COLORS.border, label: '⏸ انتظار' },
};

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_MAP[status] || STATUS_MAP.pending;
  return (
    <View style={[styles.badge, { backgroundColor: s.bg }]}>
      <Text style={[styles.badgeText, { color: s.color }]}>{s.label}</Text>
    </View>
  );
}

// ─── Document Row ─────────────────────────────────────────────

function DocRow({ doc, onPress }: { doc: Document; onPress: () => void }) {
  return (
    <TouchableOpacity style={styles.docRow} onPress={onPress} activeOpacity={0.75}>
      <View style={styles.docLeft}>
        <Text style={styles.docIcon}>{doc.fileType === 'pdf' ? '📄' : '🖼️'}</Text>
      </View>
      <View style={styles.docMiddle}>
        <Text style={styles.docName} numberOfLines={1}>{doc.filename}</Text>
        <Text style={styles.docDate}>
          {doc.createdAt ? new Date(doc.createdAt).toLocaleDateString('ar-SY') : ''}
          {doc.engine ? `  •  ${doc.engine}` : ''}
        </Text>
      </View>
      <View style={styles.docRight}>
        <StatusBadge status={doc.status} />
        {doc.confidence > 0 && (
          <Text style={[
            styles.docConf,
            { color: doc.confidence >= 90 ? COLORS.accent : doc.confidence >= 70 ? COLORS.warning : COLORS.danger }
          ]}>
            {doc.confidence}%
          </Text>
        )}
      </View>
    </TouchableOpacity>
  );
}

// ─── Filter Chips ─────────────────────────────────────────────

type Filter = 'all' | 'review' | 'completed' | 'failed';

function FilterChips({ active, onChange }: { active: Filter; onChange: (f: Filter) => void }) {
  const chips: { key: Filter; label: string }[] = [
    { key: 'all',       label: 'الكل' },
    { key: 'review',    label: '🔍 مراجعة' },
    { key: 'completed', label: '✅ مكتمل' },
    { key: 'failed',    label: '❌ فشل' },
  ];
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chips}>
      {chips.map(c => (
        <TouchableOpacity
          key={c.key}
          style={[styles.chip, active === c.key && styles.chipActive]}
          onPress={() => onChange(c.key)}
        >
          <Text style={[styles.chipText, active === c.key && styles.chipTextActive]}>
            {c.label}
          </Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

// ─── Server Status Dot ────────────────────────────────────────

function ServerDot({ online }: { online: boolean | null }) {
  const color = online === null ? '#95A5A6' : online ? COLORS.accent : COLORS.danger;
  const label = online === null ? 'جارٍ الفحص' : online ? 'الخادم متاح' : 'الخادم غير متاح';
  return (
    <View style={styles.serverDot}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={[styles.dotLabel, { color }]}>{label}</Text>
    </View>
  );
}

// ══════════════════════════════════════════════════════════════
// MAIN SCREEN
// ══════════════════════════════════════════════════════════════

export default function HomeScreen() {
  const navigation = useNavigation<any>();
  const { user } = useAuthStore();
  const { documents, setDocuments, setLoading, isLoading } = useDocumentsStore();

  const [stats, setStats]         = useState<DailyStats | null>(null);
  const [weekData, setWeekData]   = useState<number[]>([0, 0, 0, 0, 0, 0, 0]);
  const [filter, setFilter]       = useState<Filter>('all');
  const [refreshing, setRefreshing] = useState(false);
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);

  // ── Load ──────────────────────────────────────────────────

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Stats
      const s = await StatsService.getToday();
      setStats(s);

      // Week data (mock distribution for now)
      const week = [0, 0, 0, 0, 0, 0, 0];
      week[new Date().getDay()] = s.processed_today;
      setWeekData(week);

      // Documents
      const result = await DocumentService.list({ limit: 20 });
      setDocuments(result.items, result.total);

      setServerOnline(true);
    } catch {
      // Demo fallback
      setStats({
        processed_today: 14,
        accuracy_avg: 93.2,
        pending_review: 3,
        total_documents: 312,
        by_engine: { 'PaddleOCR': 8, 'TrOCR': 4, 'Tesseract': 2 },
        by_language: { 'ar': 10, 'en': 4 },
        processing_time_avg_ms: 1840,
      });
      setWeekData([3, 7, 5, 9, 14, 0, 0]);
      setServerOnline(false);

      if (documents.length === 0) {
        setDocuments([
          { id: '1', filename: 'تقرير عملية كسر عضد.jpg',   fileType: 'image', status: 'completed', confidence: 97, engine: 'TrOCR',     createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
          { id: '2', filename: 'وصفة د.أحمد 001.png',        fileType: 'image', status: 'review',    confidence: 74, engine: 'PaddleOCR', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
          { id: '3', filename: 'تقرير خروج مريض.pdf',        fileType: 'pdf',   status: 'completed', confidence: 99, engine: 'PaddleOCR', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
          { id: '4', filename: 'صورة أشعة تبايني.jpg',       fileType: 'image', status: 'failed',    confidence: 0,                       createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
          { id: '5', filename: 'مخطط تخدير عملية بطن.jpg',  fileType: 'image', status: 'completed', confidence: 88, engine: 'Tesseract', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
        ], 5);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  // ── Filter ────────────────────────────────────────────────

  const filtered = filter === 'all'
    ? documents
    : documents.filter(d => d.status === filter);

  // ── Greeting ──────────────────────────────────────────────

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'صباح الخير' : hour < 17 ? 'مساء الخير' : 'مساء النور';

  return (
    <ScrollView
      style={styles.screen}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[COLORS.primary]} />}
      showsVerticalScrollIndicator={false}
    >
      {/* ── Header ─────────────────────────────────────────── */}
      <View style={styles.header}>
        <ServerDot online={serverOnline} />
        <View style={styles.greeting}>
          <Text style={styles.greetingText}>{greeting}،</Text>
          <Text style={styles.greetingName}>{user?.name || 'دكتور'}</Text>
        </View>
        <Text style={styles.dateHeader}>
          {new Date().toLocaleDateString('ar-SY', { weekday: 'long', day: 'numeric', month: 'long' })}
        </Text>
      </View>

      <View style={styles.body}>

        {/* ── Quick Scan ────────────────────────────────────── */}
        <TouchableOpacity
          style={styles.scanBanner}
          onPress={() => navigation.navigate('Camera')}
          activeOpacity={0.85}
        >
          <View>
            <Text style={styles.scanBannerTitle}>مسح مستند جديد</Text>
            <Text style={styles.scanBannerSub}>التقط صورة أو اختر من المعرض</Text>
          </View>
          <Text style={styles.scanBannerIcon}>📷</Text>
        </TouchableOpacity>

        {/* ── Stats Grid ───────────────────────────────────── */}
        {stats && (
          <View style={styles.statsGrid}>
            <StatCard
              icon="📄" label="مُعالَج اليوم"
              value={stats.processed_today}
              color={COLORS.secondary}
            />
            <StatCard
              icon="🎯" label="دقة متوسطة"
              value={`${stats.accuracy_avg.toFixed(1)}%`}
              color={COLORS.accent}
              sub={`${Math.round(stats.processing_time_avg_ms / 1000)}ث متوسط`}
            />
            <StatCard
              icon="🔍" label="قيد المراجعة"
              value={stats.pending_review}
              color={stats.pending_review > 0 ? COLORS.warning : COLORS.textLight}
            />
            <StatCard
              icon="📁" label="إجمالي"
              value={stats.total_documents}
              color={COLORS.primary}
            />
          </View>
        )}

        {/* ── Weekly Chart ─────────────────────────────────── */}
        <WeeklyChart data={weekData} />

        {/* ── Documents ────────────────────────────────────── */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>المستندات الأخيرة</Text>
          <TouchableOpacity onPress={() => navigation.navigate('History')}>
            <Text style={styles.sectionLink}>عرض الكل</Text>
          </TouchableOpacity>
        </View>

        <FilterChips active={filter} onChange={setFilter} />

        {filtered.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>📭</Text>
            <Text style={styles.emptyText}>
              {filter === 'all' ? 'لا توجد مستندات بعد' : `لا توجد مستندات بحالة "${filter}"`}
            </Text>
            {filter === 'all' && (
              <TouchableOpacity
                style={styles.emptyBtn}
                onPress={() => navigation.navigate('Camera')}
              >
                <Text style={styles.emptyBtnText}>ابدأ بمسح أول مستند</Text>
              </TouchableOpacity>
            )}
          </View>
        ) : (
          filtered.slice(0, 10).map(doc => (
            <DocRow
              key={doc.id}
              doc={doc}
              onPress={() => navigation.navigate('OCRResult', { documentId: doc.id })}
            />
          ))
        )}

        {/* ── Engine Distribution ──────────────────────────── */}
        {stats && Object.keys(stats.by_engine).length > 0 && (
          <View style={styles.engineCard}>
            <Text style={styles.engineTitle}>توزيع المحركات اليوم</Text>
            {Object.entries(stats.by_engine).map(([engine, count]) => {
              const pct = Math.round((count / stats.processed_today) * 100) || 0;
              return (
                <View key={engine} style={styles.engineRow}>
                  <Text style={styles.engineName}>{engine}</Text>
                  <View style={styles.engineTrack}>
                    <View style={[styles.engineFill, { width: `${pct}%` }]} />
                  </View>
                  <Text style={styles.enginePct}>{pct}%</Text>
                </View>
              );
            })}
          </View>
        )}

      </View>
    </ScrollView>
  );
}

// ─── Styles ───────────────────────────────────────────────────

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },

  header: {
    backgroundColor: COLORS.primary,
    paddingTop: 16, paddingBottom: 24,
    paddingHorizontal: 20,
  },
  serverDot: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  dotLabel: { fontSize: 11 },
  greeting: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  greetingText: { fontSize: 18, color: 'rgba(255,255,255,.8)' },
  greetingName: { fontSize: 20, fontWeight: '700', color: '#fff' },
  dateHeader: { fontSize: 13, color: 'rgba(255,255,255,.65)', marginTop: 4, textAlign: 'right' },

  body: { padding: 16 },

  scanBanner: {
    backgroundColor: COLORS.secondary, borderRadius: 14,
    padding: 18, flexDirection: 'row',
    justifyContent: 'space-between', alignItems: 'center',
    marginBottom: 14, elevation: 3,
    shadowColor: COLORS.secondary, shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3, shadowRadius: 6,
  },
  scanBannerTitle: { fontSize: 17, fontWeight: '700', color: '#fff', textAlign: 'right' },
  scanBannerSub:   { fontSize: 12, color: 'rgba(255,255,255,.8)', marginTop: 2, textAlign: 'right' },
  scanBannerIcon:  { fontSize: 42 },

  statsGrid: {
    flexDirection: 'row', flexWrap: 'wrap',
    gap: 10, marginBottom: 14,
  },
  statCard: {
    width: (W - 42) / 2,
    backgroundColor: COLORS.surface, borderRadius: 12,
    padding: 14, borderTopWidth: 3, elevation: 1,
    alignItems: 'center',
  },
  statIcon:  { fontSize: 26, marginBottom: 6 },
  statValue: { fontSize: 24, fontWeight: '700' },
  statLabel: { fontSize: 12, color: COLORS.textLight, marginTop: 2, textAlign: 'center' },
  statSub:   { fontSize: 11, color: COLORS.border, marginTop: 3 },

  sectionHeader: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 8,
  },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: COLORS.text },
  sectionLink:  { fontSize: 13, color: COLORS.secondary },

  chips: { marginBottom: 10 },
  chip: {
    paddingHorizontal: 14, paddingVertical: 7,
    borderRadius: 20, backgroundColor: COLORS.surface,
    marginRight: 8, borderWidth: 1, borderColor: COLORS.border,
  },
  chipActive:     { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  chipText:       { fontSize: 13, color: COLORS.textLight },
  chipTextActive: { color: '#fff', fontWeight: '600' },

  docRow: {
    backgroundColor: COLORS.surface, borderRadius: 10,
    padding: 12, flexDirection: 'row', alignItems: 'center',
    marginBottom: 8, elevation: 1, gap: 10,
  },
  docLeft:   { },
  docIcon:   { fontSize: 28 },
  docMiddle: { flex: 1 },
  docName:   { fontSize: 14, fontWeight: '500', color: COLORS.text, textAlign: 'right' },
  docDate:   { fontSize: 11, color: COLORS.textLight, marginTop: 3, textAlign: 'right' },
  docRight:  { alignItems: 'flex-end', gap: 4 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  badgeText: { fontSize: 11, fontWeight: '600' },
  docConf: { fontSize: 13, fontWeight: '700' },

  emptyState: { alignItems: 'center', paddingVertical: 40 },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  emptyText: { fontSize: 15, color: COLORS.textLight, marginBottom: 16 },
  emptyBtn: {
    backgroundColor: COLORS.primary, borderRadius: 10,
    paddingVertical: 12, paddingHorizontal: 24,
  },
  emptyBtnText: { color: '#fff', fontWeight: '600' },

  engineCard: {
    backgroundColor: COLORS.surface, borderRadius: 12,
    padding: 14, marginTop: 6, elevation: 1,
  },
  engineTitle: { fontSize: 13, fontWeight: '600', color: COLORS.textLight, marginBottom: 12, textAlign: 'right' },
  engineRow:   { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  engineName:  { fontSize: 12, color: COLORS.text, width: 80, textAlign: 'right' },
  engineTrack: { flex: 1, height: 6, backgroundColor: COLORS.border, borderRadius: 3, overflow: 'hidden' },
  engineFill:  { height: '100%', backgroundColor: COLORS.secondary, borderRadius: 3 },
  enginePct:   { fontSize: 11, color: COLORS.textLight, width: 34, textAlign: 'right' },
});
