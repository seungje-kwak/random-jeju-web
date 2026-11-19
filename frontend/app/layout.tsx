import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./v9.css";

export const metadata: Metadata = {
  title: "Random Jeju | 랜덤 제주 여행",
  description: "주사위를 굴리면 제주 어딘가가 뽑히고, 그 근처에서 내 취향과 시간에 맞춘 하루 코스를 받아요.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#176d62",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body className="font-sans"><div className="app-shell">{children}</div></body></html>;
}
