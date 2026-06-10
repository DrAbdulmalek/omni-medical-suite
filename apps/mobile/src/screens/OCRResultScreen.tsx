/**
 * mobile/android/screens/OCRResultScreen.tsx
 * =============================================
 * شاشة نتيجة OCR الكاملة
 * - عرض النص الخام والمصحَّح جنباً إلى جنب
 * - تصحيح يدوي مع حفظ للتعلم
 * - مقارنة Word-diff بين الخام والمصحَّح
 * - تصدير: TXT / DOCX / مشاركة
 * - confidence indicator مرئي
 * - تسمية المستند وإضافة تاريخ
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, TextInput, Alert,
  Share, Animated, Keyboard,
  KeyboardAvoidingView, Platform,
  ActivityIndicator,
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useDocumentsStore } from '../store';
import { DocumentService } from '../services/api';

const COLORS = {
  primary:    '#1B4F72',
  secondary:  '#2E86C1',
  accent:     '#27AE60',
  warning:    '#E67E22',
  danger:     '#E74C3C',
  bg:         '#F4F6F7',
  surface:    '#FFFFFF',
  text:       '#1A252F',
  textLight:  '#5D6D7E',
  border:     '#D5D8DC',
};

// ─── Confidence Gauge ────────────────────────────────────────

function ConfidenceGauge({ value, engine }: { value: number; engine?: string }) {
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(anim, {
      toValue: value / 100,
      duration: 900,
      useNativeDriver: false,
    }).start();
  }, [value]);

  const color = value >= 90 ? COLORS.accent : value >= 70 ? COLORS.warning : COLORS.danger;
  const label = value >= 90 ? 'دقة عالية' : value >= 70 ? 'دقة متوسطة' : 'دقة منخفضة — يوصى بالمراجعة';

  return (
    <View style={styles.gaugeContainer}>
      <View style={styles.gaugeHeader}>
        <Text style={[styles.gaugePercent, { color }]}>{value}%</Text>
        <View>
          <Text style={styles.gaugeLabel}>{label}</Text>
          {engine && <Text style={styles.gaugeEngine}>المحرك: {engine}</Text>}
        </View>
      </View>
      <View style={styles.gaugeTrack}>
        <Animated.View style={[
          styles.gaugeFill,
          {
            backgroundColor: color,
            width: anim.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }),
          }
        ]} />
      </View>
    </View>
  );
}

// ─── Tab Switcher ────────────────────────────────────────────

type ViewMode = 'corrected' | 'raw' | 'diff';

function ViewTabs({ mode, onChange }: { mode: ViewMode; onChange: (m: ViewMode) => void }) {
  const tabs: { key: ViewMode; label: string }[] = [
    { key: 'corrected', label: 'المصحَّح' },
    { key: 'raw',       label: 'الخام' },
    { key: 'diff',      label: 'المقارنة' },
  ];
  return (
    <View style={styles.tabRow}>
      {tabs.map(t => (
        <TouchableOpacity
          key={t.key}
          style={[styles.tab, mode === t.key && styles.tabActive]}
          onPress={() => onChange(t.key)}
        >
          <Text style={[styles.tabText, mode === t.key && styles.tabTextActive]}>
            {t.label}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

// ─── Simple Word Diff ─────────────────────────────────────────

function WordDiff({ original, corrected }: { original: string; corrected: string }) {
  const origWords = original.split(/\s+/);
  const corrWords = corrected.split(/\s+/);
  const maxLen = Math.max(origWords.length, corrWords.length);

  const segments: { word: string; type: 'same' | 'changed' | 'added' | 'removed' }[] = [];

  for (let i = 0; i < maxLen; i++) {
    const o = origWords[i];
    const c = corrWords[i];
    if (!o && c)       segments.push({ word: c, type: 'added' });
    else if (o && !c)  segments.push({ word: o, type: 'removed' });
    else if (o === c)  segments.push({ word: c, type: 'same' });
    else {
      segments.push({ word: o, type: 'removed' });
      segments.push({ word: c, type: 'added' });
    }
  }

  return (
    <View style={styles.diffContainer}>
      <Text style={styles.diffHint}>🔴 محذوف &nbsp; 🟢 مُضاف &nbsp; أبيض = بدون تغيير</Text>
      <View style={styles.diffWords}>
        {segments.map((s, i) => (
          <Text key={i} style={[
            styles.diffWord,
            s.type === 'added'   && styles.diffAdded,
            s.type === 'removed' && styles.diffRemoved,
          ]}>
            {s.word}{' '}
          </Text>
        ))}
      </View>
    </View>
  );
}

// ─── Export Menu ─────────────────────────────────────────────

function ExportMenu({
  documentId, text, onClose
}: { documentId: string; text: string; onClose: () => void }) {
  const [loading, setLoading] = useState(false);

  const handleShare = async () => {
    onClose();
    await Share.share({ message: text, title: 'نص OCR المُستخرج' });
  };

  const handleExportTxt = async () => {
    setLoading(true);
    try {
      const { url } = await DocumentService.export(documentId, 'txt');
      onClose();
      Alert.alert('✅ تم التصدير', `يمكن تحميل الملف من:\n${url}`);
    } catch {
      Alert.alert('خطأ', 'تعذّر تصدير الملف');
    } finally {
      setLoading(false);
    }
  };

  const handleExportDocx = async () => {
    setLoading(true);
    try {
      const { url } = await DocumentService.export(documentId, 'docx');
      onClose();
      Alert.alert('✅ تم التصدير', `ملف Word جاهز:\n${url}`);
    } catch {
      Alert.alert('خطأ', 'تعذّر تصدير Word');
    } finally {
      setLoading(false);
    }
  };

  const options = [
    { icon: '📤', label: 'مشاركة النص', action: handleShare },
    { icon: '📝', label: 'تصدير TXT', action: handleExportTxt },
    { icon: '📄', label: 'تصدير Word (.docx)', action: handleExportDocx },
  ];

  return (
    <View style={styles.exportMenu}>
      {loading && <ActivityIndicator color={COLORS.primary} style={{ marginBottom: 8 }} />}
      {options.map((o, i) => (
        <TouchableOpacity key={i} style={styles.exportOption} onPress={o.action} disabled={loading}>
          <Text style={styles.exportIcon}>{o.icon}</Text>
          <Text style={styles.exportLabel}>{o.label}</Text>
        </TouchableOpacity>
      ))}
      <TouchableOpacity style={styles.exportCancel} onPress={onClose}>
        <Text style={styles.exportCancelText}>إلغاء</Text>
      </TouchableOpacity>
    </View>
  );
}

// ══════════════════════════════════════════════════════════════
// MAIN SCREEN
// ══════════════════════════════════════════════════════════════

export default function OCRResultScreen() {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { documentId } = route.params || {};

  const { getById, updateDocument } = useDocumentsStore();
  const doc = getById(documentId);

  const [viewMode, setViewMode] = useState<ViewMode>('corrected');
  const [editText, setEditText] = useState(doc?.correctedText || '');
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [docLabel, setDocLabel] = useState(doc?.filename || '');
  const [labelEditing, setLabelEditing] = useState(false);
  const inputRef = useRef<TextInput>(null);

  useEffect(() => {
    if (doc) {
      setEditText(doc.correctedText || doc.rawText || '');
      setDocLabel(doc.filename || '');
    }
  }, [doc]);

  // ── Save Correction ───────────────────────────────────────

  const handleSave = useCallback(async () => {
    if (!documentId || !editText.trim()) return;
    setSaving(true);
    Keyboard.dismiss();
    try {
      await DocumentService.saveCorrection(documentId, editText);
      updateDocument(documentId, {
        correctedText: editText,
        status: 'completed',
        filename: docLabel || doc?.filename,
      });
      setIsEditing(false);
      Alert.alert(
        '✅ تم الحفظ',
        'تم حفظ التصحيح وسيُستخدم لتحسين دقة التعرف مستقبلاً.',
        [{ text: 'حسناً' }]
      );
    } catch {
      Alert.alert('خطأ', 'تعذّر حفظ التصحيح — تحقق من الاتصال');
    } finally {
      setSaving(false);
    }
  }, [documentId, editText, docLabel, doc]);

  // ── Discard Edits ─────────────────────────────────────────

  const handleDiscard = useCallback(() => {
    Alert.alert('تجاهل التغييرات؟', 'سيتم إلغاء التعديلات غير المحفوظة.', [
      { text: 'متابعة التعديل', style: 'cancel' },
      {
        text: 'تجاهل', style: 'destructive',
        onPress: () => {
          setEditText(doc?.correctedText || doc?.rawText || '');
          setIsEditing(false);
        },
      },
    ]);
  }, [doc]);

  if (!doc) {
    return (
      <View style={[styles.screen, { alignItems: 'center', justifyContent: 'center' }]}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>جارٍ تحميل النتيجة…</Text>
      </View>
    );
  }

  const rawText       = doc.rawText || '';
  const correctedText = doc.correctedText || rawText;
  const confidence    = doc.confidence || 0;
  const hasChanges    = editText !== correctedText;

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >

        {/* ── Label ────────────────────────────────────────── */}
        <View style={styles.labelRow}>
          {labelEditing ? (
            <TextInput
              style={styles.labelInput}
              value={docLabel}
              onChangeText={setDocLabel}
              onBlur={() => setLabelEditing(false)}
              autoFocus
              textAlign="right"
              placeholder="اسم المستند"
            />
          ) : (
            <TouchableOpacity onPress={() => setLabelEditing(true)} style={styles.labelButton}>
              <Text style={styles.labelText}>{docLabel || 'مستند بدون اسم'}</Text>
              <Text style={styles.labelEdit}>✏️</Text>
            </TouchableOpacity>
          )}
          <Text style={styles.dateText}>
            {doc.createdAt ? new Date(doc.createdAt).toLocaleDateString('ar-SY') : ''}
          </Text>
        </View>

        {/* ── Confidence ───────────────────────────────────── */}
        <ConfidenceGauge value={confidence} engine={doc.engine} />

        {/* ── View Mode Tabs ───────────────────────────────── */}
        <ViewTabs mode={viewMode} onChange={setViewMode} />

        {/* ── Text Area ────────────────────────────────────── */}
        {viewMode === 'diff' ? (
          <WordDiff original={rawText} corrected={correctedText} />
        ) : viewMode === 'raw' ? (
          <View style={styles.textBox}>
            <Text style={styles.rawText}>{rawText || 'لا يوجد نص خام'}</Text>
          </View>
        ) : isEditing ? (
          <TextInput
            ref={inputRef}
            style={styles.editInput}
            value={editText}
            onChangeText={setEditText}
            multiline
            textAlign="right"
            textAlignVertical="top"
            placeholder="عدّل النص هنا…"
            autoFocus
          />
        ) : (
          <TouchableOpacity
            style={styles.textBox}
            onLongPress={() => { setIsEditing(true); inputRef.current?.focus(); }}
            activeOpacity={0.85}
          >
            <Text style={styles.correctedText}>{correctedText || 'لا يوجد نص'}</Text>
            <Text style={styles.tapHint}>اضغط مطوّلاً للتعديل</Text>
          </TouchableOpacity>
        )}

        {/* ── Word Count ───────────────────────────────────── */}
        <View style={styles.metaRow}>
          <Text style={styles.metaText}>
            {correctedText.split(/\s+/).filter(Boolean).length} كلمة
          </Text>
          <Text style={styles.metaText}>
            {correctedText.length} حرف
          </Text>
          {hasChanges && (
            <Text style={[styles.metaText, { color: COLORS.warning }]}>● تعديلات غير محفوظة</Text>
          )}
        </View>

        {/* ── Actions ──────────────────────────────────────── */}
        <View style={styles.actionsRow}>
          {isEditing ? (
            <>
              <TouchableOpacity
                style={[styles.btn, styles.btnPrimary, saving && { opacity: 0.6 }]}
                onPress={handleSave}
                disabled={saving}
              >
                {saving
                  ? <ActivityIndicator color="#fff" size="small" />
                  : <Text style={styles.btnPrimaryText}>💾 حفظ التصحيح</Text>
                }
              </TouchableOpacity>
              <TouchableOpacity style={[styles.btn, styles.btnSecondary]} onPress={handleDiscard}>
                <Text style={styles.btnSecondaryText}>↩️ إلغاء</Text>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <TouchableOpacity
                style={[styles.btn, styles.btnPrimary]}
                onPress={() => { setIsEditing(true); }}
              >
                <Text style={styles.btnPrimaryText}>✏️ تعديل</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.btn, styles.btnSecondary]}
                onPress={() => setShowExport(true)}
              >
                <Text style={styles.btnSecondaryText}>📤 تصدير</Text>
              </TouchableOpacity>
            </>
          )}
        </View>

        {/* ── New Scan ─────────────────────────────────────── */}
        <TouchableOpacity
          style={styles.newScanBtn}
          onPress={() => navigation.navigate('Camera')}
        >
          <Text style={styles.newScanText}>📷 مسح مستند جديد</Text>
        </TouchableOpacity>

      </ScrollView>

      {/* ── Export Sheet ─────────────────────────────────── */}
      {showExport && (
        <View style={styles.sheet}>
          <ExportMenu
            documentId={documentId}
            text={editText}
            onClose={() => setShowExport(false)}
          />
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

// ─── Styles ───────────────────────────────────────────────────

const styles = StyleSheet.create({
  screen:  { flex: 1, backgroundColor: COLORS.bg },
  scroll:  { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },
  loadingText: { marginTop: 12, color: COLORS.textLight },

  // Label
  labelRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 12,
  },
  labelButton: { flexDirection: 'row', alignItems: 'center', gap: 6, flex: 1 },
  labelText:   { fontSize: 15, fontWeight: '600', color: COLORS.text, textAlign: 'right' },
  labelEdit:   { fontSize: 14 },
  labelInput:  {
    flex: 1, borderBottomWidth: 1.5, borderBottomColor: COLORS.secondary,
    fontSize: 15, color: COLORS.text, paddingBottom: 4,
  },
  dateText:    { fontSize: 12, color: COLORS.textLight, marginLeft: 8 },

  // Gauge
  gaugeContainer: {
    backgroundColor: COLORS.surface, borderRadius: 12,
    padding: 14, marginBottom: 12, elevation: 1,
  },
  gaugeHeader: {
    flexDirection: 'row', alignItems: 'center',
    gap: 12, marginBottom: 10,
  },
  gaugePercent: { fontSize: 32, fontWeight: '700' },
  gaugeLabel:   { fontSize: 13, color: COLORS.text, fontWeight: '600', textAlign: 'right' },
  gaugeEngine:  { fontSize: 11, color: COLORS.textLight, textAlign: 'right' },
  gaugeTrack:   { height: 8, backgroundColor: COLORS.border, borderRadius: 4, overflow: 'hidden' },
  gaugeFill:    { height: '100%', borderRadius: 4 },

  // Tabs
  tabRow:       { flexDirection: 'row', marginBottom: 10, gap: 8 },
  tab:          {
    flex: 1, paddingVertical: 8, borderRadius: 8,
    backgroundColor: COLORS.surface, alignItems: 'center',
    borderWidth: 1, borderColor: COLORS.border,
  },
  tabActive:    { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  tabText:      { fontSize: 13, color: COLORS.textLight, fontWeight: '500' },
  tabTextActive: { color: '#fff', fontWeight: '700' },

  // Text
  textBox: {
    backgroundColor: COLORS.surface, borderRadius: 12,
    padding: 14, minHeight: 160,
    borderWidth: 1, borderColor: COLORS.border, marginBottom: 8,
  },
  rawText:       { fontSize: 14, color: COLORS.textLight, textAlign: 'right', lineHeight: 24 },
  correctedText: { fontSize: 15, color: COLORS.text, textAlign: 'right', lineHeight: 26 },
  tapHint:       { fontSize: 11, color: COLORS.border, textAlign: 'center', marginTop: 12 },
  editInput: {
    backgroundColor: COLORS.surface, borderRadius: 12,
    padding: 14, minHeight: 200, marginBottom: 8,
    fontSize: 15, color: COLORS.text, lineHeight: 26,
    borderWidth: 1.5, borderColor: COLORS.secondary,
    textAlignVertical: 'top',
  },

  // Diff
  diffContainer: {
    backgroundColor: COLORS.surface, borderRadius: 12,
    padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: COLORS.border,
  },
  diffHint:  { fontSize: 11, color: COLORS.textLight, marginBottom: 10, textAlign: 'right' },
  diffWords: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'flex-end' },
  diffWord:  { fontSize: 14, lineHeight: 24, color: COLORS.text },
  diffAdded:   { backgroundColor: '#D5F5E3', color: '#1E8449', borderRadius: 3, paddingHorizontal: 2 },
  diffRemoved: { backgroundColor: '#FADBD8', color: '#922B21', textDecorationLine: 'line-through', borderRadius: 3 },

  // Meta
  metaRow: {
    flexDirection: 'row', justifyContent: 'flex-end',
    gap: 12, marginBottom: 14,
  },
  metaText: { fontSize: 12, color: COLORS.textLight },

  // Buttons
  actionsRow: { flexDirection: 'row', gap: 10, marginBottom: 10 },
  btn:            { flex: 1, borderRadius: 10, paddingVertical: 14, alignItems: 'center' },
  btnPrimary:     { backgroundColor: COLORS.primary },
  btnPrimaryText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  btnSecondary:   { backgroundColor: COLORS.surface, borderWidth: 1.5, borderColor: COLORS.secondary },
  btnSecondaryText: { color: COLORS.secondary, fontWeight: '600', fontSize: 15 },
  newScanBtn: {
    backgroundColor: COLORS.bg, borderRadius: 10,
    padding: 14, alignItems: 'center',
    borderWidth: 1, borderColor: COLORS.border,
  },
  newScanText: { color: COLORS.textLight, fontSize: 14 },

  // Export sheet
  sheet: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    backgroundColor: 'rgba(0,0,0,.4)',
    flex: 1, justifyContent: 'flex-end',
  },
  exportMenu: {
    backgroundColor: COLORS.surface,
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    padding: 20, paddingBottom: 36,
  },
  exportOption: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingVertical: 14, borderBottomWidth: 0.5, borderBottomColor: COLORS.border,
  },
  exportIcon:   { fontSize: 22 },
  exportLabel:  { fontSize: 15, color: COLORS.text, fontWeight: '500' },
  exportCancel: { marginTop: 12, alignItems: 'center' },
  exportCancelText: { color: COLORS.danger, fontSize: 15, fontWeight: '600' },
});
