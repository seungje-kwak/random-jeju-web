"use client";
// tasks/prd-random-jeju-merge.md 3.2: four tabs. A bar along the bottom on phones; a row under the header on
// wide screens. Course, trip and onboarding screens do not show it.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MESSAGES, useLocale } from "@/lib/i18n";

const TABS = [
  { href: "/random", icon: "🎲", key: "random" },
  { href: "/map", icon: "🗺️", key: "map" },
  { href: "/feed", icon: "📰", key: "feed" },
  { href: "/upload", icon: "➕", key: "upload" },
] as const;

export function TabBar() {
  const path = usePathname();
  const t = MESSAGES[useLocale().locale].social;
  const links = (cls: string) =>
    TABS.map((tab) => {
      const active = path === tab.href || path?.startsWith(`${tab.href}/`);
      return (
        <Link key={tab.href} href={tab.href} aria-current={active ? "page" : undefined}
          className={`${cls} ${active ? "text-[var(--sea)] font-extrabold" : "text-[#56767b]"}`}>
          <span aria-hidden="true">{tab.icon}</span>
          <span>{t.tabs[tab.key]}</span>
        </Link>
      );
    });
  return (
    <>
      <nav aria-label={t.tabsLabel}
        className="fixed inset-x-0 bottom-0 z-50 grid grid-cols-4 border-t border-[var(--line)] bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
        {links("flex flex-col items-center gap-0.5 py-2 text-[11px] font-bold")}
      </nav>
      <nav aria-label={t.tabsLabel} className="hidden border-b border-[var(--line)] bg-white px-6 lg:flex lg:gap-1">
        {links("flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold hover:bg-[#eff5f2]")}
      </nav>
    </>
  );
}

/** Space so the last content is not hidden under the phone tab bar. */
export function TabBarSpacer() {
  return <div aria-hidden="true" className="h-20 lg:hidden" />;
}
