import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'Nola · 情感陪伴与智能推荐 Demo',
  description: '单张头像、自然聊天、情绪化回复与 Onely 套餐推荐的前端交互 Demo。',
  openGraph: {
    title: 'Nola · 虚拟达人 Demo',
    description: '聊天、情感陪伴与智能推荐',
    images: [{ url: '/og.png', width: 1664, height: 946, alt: 'Nola 虚拟达人 Demo' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Nola · 虚拟达人 Demo',
    description: '聊天、情感陪伴与智能推荐',
    images: ['/og.png'],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>{children}</body>
    </html>
  );
}
