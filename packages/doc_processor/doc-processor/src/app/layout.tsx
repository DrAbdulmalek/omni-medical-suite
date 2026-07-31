import type { Metadata } from "next";
import { Noto_Sans_Arabic } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as SonnerToaster } from "sonner";
import { ThemeProvider } from "@/components/ThemeProvider";
import { AuthProvider } from "@/components/Providers";

const notoArabic = Noto_Sans_Arabic({
  variable: "--font-noto-arabic",
  subsets: ["arabic"],
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "معالج المستندات الطبية",
  description: "تطبيق ويب شامل لمعالجة صور المستندات الطبية الممسوحة ضوئياً",
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <body
        className={`${notoArabic.variable} font-[family-name:var(--font-noto-arabic)] antialiased bg-slate-50 text-slate-900`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          <AuthProvider>
            {children}
          </AuthProvider>
          <Toaster />
          <SonnerToaster position="top-left" dir="rtl" richColors closeButton />
        </ThemeProvider>
      </body>
    </html>
  );
}
