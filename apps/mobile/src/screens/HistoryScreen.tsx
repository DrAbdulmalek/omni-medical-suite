/**
 * mobile/android/screens/HistoryScreen.tsx
 * ===========================================
 * شاشة السجل الكامل
 * - بحث نصي في أسماء الملفات والنص المستخرج
 * - فلترة: الكل / مراجعة / مكتمل / فشل
 * - ترتيب: تاريخ / دقة / اسم
 * - سحب للتحديث + pagination
 * - حذف مع تأكيد
 */

import React, { useCallback, useEffect, useState, useRef } from 'react';
import {
  View, Text, StyleSheet, FlatList,
  TouchableOpacity, TextInput, RefreshControl,
  Alert, Animated,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useDocumentsStore } from '../store';
import { DocumentService } from '../services/api';
import type { Document } from '../store';

const COLORS = {
  primary: '#1B4F72', secondary: '#2E86C1',
  accent: '#27AE60', warning: '#E67E22',
  danger: '#E74C3C', bg: '#F4F6F7',
  surface: '#FFFFFF', text: '#1A252F',
  textLight: '#5D6D7E', border: '#D5D8DC',
};

type SortKey  = 'date' | 'confidence' | 'name';
type FilterKey = 'all' | 'completed' | 'review' | 'failed';

// ─── Swipeable Row (simplified) ──────────────────────────────

function DocCard({
  doc, onPress, onDelete,
}: { doc: Document; onPress: () => void; onDelete: () => void }) {
  const slideAnim = useRef(new Animated.Value(1)).current;

  const confirmDelete = () => {
    Alert.alert(
      'حذف المستند',
      `هل تريد حذف "${doc.filename}"؟ لا يمكن التراجع.`,
      [
        { text: 'إلغاء', style: 'cancel' },
        {
          text: 'حذف', style: 'destructive',
          onPress: () => {
            Animated.timing(slideAnim, {
              toValue: 0, duration: 250, useNativeDriver: true,
            }).start(onDelete);
          },
        },
      ]
    );
  };

  const statusInfo = {
    completed:  { color: COLORS.accent,    bg: '#D5F5E3', label: '✅ مكتمل' },
    review:     { color: COLORS.warning,   bg: '#FDEBD0', label: '🔍 مراجعة' },
    processing: { color: COLORS.secondary, bg: '#D6EAF8', label: '⏳ جارٍ' },
    failed:     { color: COLORS.danger,    bg: '#FADBD8', label: '❌ فشل' },
    pending:    { color: COLORS.textLight, bg: COLORS.border, label: '⏸ انتظار' },
  }[doc.status] || { color: COLORS.textLight, bg: COLORS.border, label: doc.status };

  return (
    <Animated.View style={{ opacity: slideAnim, transform: [{ scaleY: slideAnim }] }}>
      <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.8}>
        <View style={styles.cardLeft}>
          <Text style={styles.cardIcon}>{doc.fileType === 'pdf' ? '📄' : '🖼️'}</Text>
        </View>

        <View style={styles.cardBody}>
          <Text style={styles.cardName} numberOfLines={1}>{doc.filename}</Text>
          <View style={styles.cardMeta}>
            {doc.engine && <Text style={styles.cardMetaText}>{doc.engine}</Text>}
            <Text style={styles.cardMetaText}>
              {doc.createdAt
                ? new Date(doc.createdAt).toLocaleDateString('ar-SY', { month: 'short', day: 'numeric' })
                : ''}
            </Text>
          </View>
          {doc.correctedText && (
            <Text style={styles.cardPreview} numberOfLines={1}>
              {doc.correctedText.slice(0, 60)}…
            </Text>
          )}
        </View>

        <View style={styles.cardRight}>
          <View style={[styles.statusBadge, { backgroundColor: statusInfo.bg }]}>
            <Text style={[styles.statusText, { color: statusInfo.color }]}>{statusInfo.label}</Text>
          </View>
          {doc.confidence > 0 && (
            <Text style={[
              styles.confText,
              { color: doc.confidence >= 90 ? COLORS.accent : doc.confidence >= 70 ? COLORS.warning : COLORS.danger }
            ]}>
              {doc.confidence}%
            </Text>
          )}
          <TouchableOpacity onPress={confirmDelete} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Text style={styles.deleteIcon}>🗑️</Text>
          </TouchableOpacity>
        </View>
      </TouchableOpacity>
    </Animated.View>
  );
}

// ─── Sort Bar ────────────────────────────────────────────────

function SortBar({
  sort, filter, onSort, onFilter,
}: {
  sort: SortKey; filter: FilterKey;
  onSort: (s: SortKey) => void;
  onFilter: (f: FilterKey) => void;
}) {
  return (
    <View style={styles.controlBar}>
      <View style={styles.sortRow}>
        <Text style={styles.controlLabel}>ترتيب:</Text>
        {(['date', 'confidence', 'name'] as SortKey[]).map(s => (
          <TouchableOpacity
            key={s}
            style={[styles.sortChip, sort === s && styles.sortChipActive]}
            onPress={() => onSort(s)}
          >
            <Text style={[styles.sortChipText, sort === s && styles.sortChipTextActive]}>
              {s === 'date' ? '📅 تاريخ' : s === 'confidence' ? '🎯 دقة' : '🔤 اسم'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.filterRow}>
        {(['all', 'review', 'completed', 'failed'] as FilterKey[]).map(f => (
          <TouchableOpacity
            key={f}
            style={[styles.filterChip, filter === f && styles.filterChipActive]}
            onPress={() => onFilter(f)}
          >
            <Text style={[styles.filterChipText, filter === f && styles.filterChipTextActive]}>
              {f === 'all' ? 'الكل' : f === 'review' ? 'مراجعة' : f === 'completed' ? 'مكتمل' : 'فشل'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

// ══════════════════════════════════════════════════════════════
// MAIN SCREEN
// ══════════════════════════════════════════════════════════════

export default function HistoryScreen() {
  const navigation = useNavigation<any>();
  const { documents, setDocuments, removeDocument, totalCount } = useDocumentsStore();

  const [search,    setSearch]    = useState('');
  const [sort,      setSort]      = useState<SortKey>('date');
  const [filter,    setFilter]    = useState<FilterKey>('all');
  const [page,      setPage]      = useState(1);
  const [loading,   setLoading]   = useState(false);
  const [refreshing,setRefreshing]= useState(false);
  const [hasMore,   setHasMore]   = useState(true);

  const PER_PAGE = 20;

  // ── Load ──────────────────────────────────────────────────

  const load = useCallback(async (reset = false) => {
    if (loading && !reset) return;
    setLoading(true);
    const currentPage = reset ? 1 : page;

    try {
      const result = await DocumentService.list({
        page: currentPage,
        limit: PER_PAGE,
        status: filter !== 'all' ? filter as Document['status'] : undefined,
        search: search || undefined,
      });

      if (reset) {
        setDocuments(result.items, result.total);
        setPage(2);
      } else {
        setDocuments([...documents, ...result.items], result.total);
        setPage(p => p + 1);
      }
      setHasMore(result.has_next);
    } catch {
      if (reset && documents.length === 0) {
        // demo fallback — keep existing
      }
    } finally {
      setLoading(false);
    }
  }, [filter, search, page, loading, documents]);

  useEffect(() => { load(true); }, [filter, search]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load(true);
    setRefreshing(false);
  }, [load]);

  const onEndReached = useCallback(() => {
    if (hasMore && !loading) load(false);
  }, [hasMore, loading, load]);

  // ── Delete ────────────────────────────────────────────────

  const handleDelete = useCallback(async (id: string) => {
    try {
      await DocumentService.delete(id);
      removeDocument(id);
    } catch {
      Alert.alert('خطأ', 'تعذّر حذف المستند');
    }
  }, [removeDocument]);

  // ── Filter + Sort local ───────────────────────────────────

  const displayed = documents
    .filter(d => {
      const matchFilter = filter === 'all' || d.status === filter;
      const matchSearch = !search
        || d.filename.toLowerCase().includes(search.toLowerCase())
        || (d.correctedText || '').includes(search)
        || (d.rawText || '').includes(search);
      return matchFilter && matchSearch;
    })
    .sort((a, b) => {
      if (sort === 'confidence') return (b.confidence || 0) - (a.confidence || 0);
      if (sort === 'name') return a.filename.localeCompare(b.filename);
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    });

  // ── Render ────────────────────────────────────────────────

  return (
    <View style={styles.screen}>

      {/* Search */}
      <View style={styles.searchContainer}>
        <Text style={styles.searchIcon}>🔍</Text>
        <TextInput
          style={styles.searchInput}
          value={search}
          onChangeText={setSearch}
          placeholder="ابحث في المستندات والنصوص…"
          placeholderTextColor={COLORS.textLight}
          textAlign="right"
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
        {search.length > 0 && (
          <TouchableOpacity onPress={() => setSearch('')}>
            <Text style={styles.clearSearch}>✕</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Controls */}
      <SortBar sort={sort} filter={filter} onSort={setSort} onFilter={setFilter} />

      {/* Count */}
      <View style={styles.countRow}>
        <Text style={styles.countText}>
          {displayed.length} من {totalCount} مستند
          {search ? ` · نتائج "${search}"` : ''}
        </Text>
      </View>

      {/* List */}
      <FlatList
        data={displayed}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <DocCard
            doc={item}
            onPress={() => navigation.navigate('OCRResult', { documentId: item.id })}
            onDelete={() => handleDelete(item.id)}
          />
        )}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[COLORS.primary]} />
        }
        onEndReached={onEndReached}
        onEndReachedThreshold={0.3}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>📭</Text>
            <Text style={styles.emptyText}>
              {search ? `لا نتائج لـ "${search}"` : 'لا توجد مستندات بعد'}
            </Text>
          </View>
        }
        ListFooterComponent={
          hasMore && !refreshing
            ? <Text style={styles.loadingMore}>جارٍ التحميل…</Text>
            : null
        }
      />
    </View>
  );
}

// ─── Styles ───────────────────────────────────────────────────

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },

  searchContainer: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: COLORS.surface,
    margin: 12, borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 8,
    borderWidth: 1, borderColor: COLORS.border, gap: 8,
  },
  searchIcon:  { fontSize: 16 },
  searchInput: { flex: 1, fontSize: 14, color: COLORS.text },
  clearSearch: { fontSize: 14, color: COLORS.textLight, padding: 4 },

  controlBar: { paddingHorizontal: 12, gap: 8, marginBottom: 6 },
  sortRow:    { flexDirection: 'row', alignItems: 'center', gap: 8 },
  filterRow:  { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  controlLabel: { fontSize: 12, color: COLORS.textLight },

  sortChip:         { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 16, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border },
  sortChipActive:   { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  sortChipText:     { fontSize: 12, color: COLORS.textLight },
  sortChipTextActive: { color: '#fff', fontWeight: '600' },

  filterChip:         { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 16, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border },
  filterChipActive:   { backgroundColor: COLORS.secondary, borderColor: COLORS.secondary },
  filterChipText:     { fontSize: 12, color: COLORS.textLight },
  filterChipTextActive: { color: '#fff', fontWeight: '600' },

  countRow:  { paddingHorizontal: 14, paddingBottom: 6 },
  countText: { fontSize: 12, color: COLORS.textLight, textAlign: 'right' },

  list: { paddingHorizontal: 12, paddingBottom: 32 },

  card: {
    backgroundColor: COLORS.surface, borderRadius: 12,
    padding: 12, flexDirection: 'row',
    alignItems: 'center', marginBottom: 8,
    elevation: 1, gap: 10,
  },
  cardLeft:   { },
  cardIcon:   { fontSize: 32 },
  cardBody:   { flex: 1, gap: 3 },
  cardName:   { fontSize: 13, fontWeight: '600', color: COLORS.text, textAlign: 'right' },
  cardMeta:   { flexDirection: 'row', gap: 8, justifyContent: 'flex-end' },
  cardMetaText: { fontSize: 11, color: COLORS.textLight },
  cardPreview:  { fontSize: 11, color: COLORS.textLight, fontStyle: 'italic', textAlign: 'right' },
  cardRight:  { alignItems: 'flex-end', gap: 5 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  statusText:  { fontSize: 11, fontWeight: '600' },
  confText:    { fontSize: 14, fontWeight: '700' },
  deleteIcon:  { fontSize: 18, opacity: 0.5 },

  empty: { alignItems: 'center', paddingVertical: 60 },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  emptyText: { fontSize: 15, color: COLORS.textLight },
  loadingMore: { textAlign: 'center', color: COLORS.textLight, fontSize: 13, padding: 16 },
});
