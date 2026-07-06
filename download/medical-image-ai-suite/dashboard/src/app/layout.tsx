import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

// ============================================================================
// Font Configuration
// ============================================================================

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

// ============================================================================
// Metadata
// ============================================================================

export const metadata: Metadata = {
  title: 'OmniMedical Training Dashboard',
  description:
    'Real-time monitoring dashboard for Arabic medical OCR model training — metrics, deployments, and data collection.',
  keywords: ['medical OCR', 'Arabic', 'training dashboard', 'machine learning', 'TrOCR'],
  authors: [{ name: 'OmniMedical AI Team' }],
  manifest: '/manifest.json',
  themeColor: '#0a0a1a',
};

// ============================================================================
// Root Layout
// ============================================================================

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" dir="auto" className="dark">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="color-scheme" content="dark" />
      </head>
      <body
        className={`${inter.variable} min-h-screen bg-gray-950 font-sans antialiased text-white`}
      >
        {children}
      </body>
    </html>
  );
}
