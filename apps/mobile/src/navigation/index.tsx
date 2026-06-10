/**
 * mobile/android/navigation/index.tsx
 * ======================================
 * إعداد التنقل الكامل مع Deep Linking
 */

import React from 'react';
import { NavigationContainer, LinkingOptions } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text, View, TouchableOpacity } from 'react-native';
import { useAuthStore } from '../store';

// ─── Screen Imports ───────────────────────────────────────────
import SplashScreen    from '../screens/SplashScreen';
import LoginScreen     from '../screens/LoginScreen';
import HomeScreen      from '../screens/HomeScreen';
import CameraScreen    from '../screens/CameraScreen';
import ImagePreviewScreen from '../screens/ImagePreviewScreen';
import OCRResultScreen from '../screens/OCRResultScreen';
import HistoryScreen   from '../screens/HistoryScreen';
import SettingsScreen  from '../screens/SettingsScreen';

// ─── Types ────────────────────────────────────────────────────

export type RootStackParamList = {
  Splash: undefined;
  Login: undefined;
  Main: undefined;
  Camera: undefined;
  ImagePreview: { imageUri: string; isPdf?: boolean };
  OCRResult: { documentId: string; imageUri?: string };
};

export type MainTabParamList = {
  Home: undefined;
  Scan: undefined;
  History: undefined;
  Settings: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tab   = createBottomTabNavigator<MainTabParamList>();

// ─── Deep Linking ─────────────────────────────────────────────

const linking: LinkingOptions<RootStackParamList> = {
  prefixes: ['omnimedical://', 'https://app.omni-medical.dev'],
  config: {
    screens: {
      Login:       'login',
      Main:        '',
      OCRResult:   'documents/:documentId',
      ImagePreview: 'preview',
    },
  },
};

// ─── Tab Bar Icons ────────────────────────────────────────────

function TabIcon({ icon, label, focused }: { icon: string; label: string; focused: boolean }) {
  return (
    <View style={{ alignItems: 'center', gap: 2 }}>
      <Text style={{ fontSize: 22, opacity: focused ? 1 : 0.5 }}>{icon}</Text>
      <Text style={{
        fontSize: 11,
        color: focused ? '#1B4F72' : '#95A5A6',
        fontWeight: focused ? '600' : '400',
      }}>{label}</Text>
    </View>
  );
}

// ─── Badge (pending review count) ────────────────────────────

function BadgeIcon({ icon, label, focused, count }: any) {
  return (
    <View style={{ alignItems: 'center', gap: 2 }}>
      <View>
        <Text style={{ fontSize: 22, opacity: focused ? 1 : 0.5 }}>{icon}</Text>
        {count > 0 && (
          <View style={{
            position: 'absolute', top: -4, right: -8,
            backgroundColor: '#E74C3C', borderRadius: 8,
            minWidth: 16, height: 16, alignItems: 'center', justifyContent: 'center',
          }}>
            <Text style={{ color: '#fff', fontSize: 10, fontWeight: '700' }}>
              {count > 9 ? '9+' : count}
            </Text>
          </View>
        )}
      </View>
      <Text style={{
        fontSize: 11,
        color: focused ? '#1B4F72' : '#95A5A6',
        fontWeight: focused ? '600' : '400',
      }}>{label}</Text>
    </View>
  );
}

// ─── Main Tabs ──────────────────────────────────────────────

function MainTabs() {
  const pendingCount = 3; // من useDocumentsStore في التطبيق الحقيقي

  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#1B4F72' },
        headerTintColor: '#fff',
        headerTitleAlign: 'center',
        headerTitleStyle: { fontWeight: '600' },
        tabBarShowLabel: false,
        tabBarStyle: {
          height: 64,
          paddingBottom: 8,
          borderTopWidth: 0.5,
          borderTopColor: '#D5D8DC',
          elevation: 8,
          shadowColor: '#000',
          shadowOffset: { width: 0, height: -2 },
          shadowOpacity: 0.06,
          shadowRadius: 4,
        },
      }}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{
          title: 'الرئيسية',
          tabBarIcon: ({ focused }) => <TabIcon icon="🏠" label="الرئيسية" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Scan"
        component={CameraScreen}
        options={{
          title: 'مسح مستند',
          headerShown: false,
          tabBarIcon: ({ focused }) => (
            <View style={{
              width: 56, height: 56, borderRadius: 28,
              backgroundColor: '#1B4F72',
              alignItems: 'center', justifyContent: 'center',
              marginBottom: 16,
              shadowColor: '#1B4F72',
              shadowOffset: { width: 0, height: 4 },
              shadowOpacity: 0.4,
              shadowRadius: 8,
              elevation: 8,
            }}>
              <Text style={{ fontSize: 26 }}>📷</Text>
            </View>
          ),
        }}
      />
      <Tab.Screen
        name="History"
        component={HistoryScreen}
        options={{
          title: 'السجل',
          tabBarIcon: ({ focused }) => (
            <BadgeIcon icon="📋" label="السجل" focused={focused} count={pendingCount} />
          ),
        }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          title: 'الإعدادات',
          tabBarIcon: ({ focused }) => <TabIcon icon="⚙️" label="إعدادات" focused={focused} />,
        }}
      />
    </Tab.Navigator>
  );
}

// ─── Root Navigator ───────────────────────────────────────────

export default function AppNavigator() {
  const { isAuthenticated } = useAuthStore();

  return (
    <NavigationContainer linking={linking}>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: '#1B4F72' },
          headerTintColor: '#fff',
          headerTitleAlign: 'center',
          animation: 'slide_from_right',
        }}
      >
        <Stack.Screen name="Splash" component={SplashScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Login"  component={LoginScreen}  options={{ headerShown: false }} />
        <Stack.Screen name="Main"   component={MainTabs}     options={{ headerShown: false }} />
        <Stack.Screen
          name="ImagePreview"
          component={ImagePreviewScreen}
          options={{ title: 'معاينة المستند' }}
        />
        <Stack.Screen
          name="OCRResult"
          component={OCRResultScreen}
          options={({ navigation }) => ({
            title: 'نتيجة OCR',
            headerRight: () => (
              <TouchableOpacity onPress={() => navigation.navigate('Main')} style={{ marginRight: 4 }}>
                <Text style={{ color: '#fff', fontSize: 13 }}>الرئيسية</Text>
              </TouchableOpacity>
            ),
          })}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
