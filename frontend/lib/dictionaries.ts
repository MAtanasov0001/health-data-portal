import "server-only";

import type { Locale } from "@/i18n-config";
import bg from "@/lib/dictionaries/bg.json";
import en from "@/lib/dictionaries/en.json";

export type Dictionary = typeof bg;

const dictionaries: Record<Locale, Dictionary> = { bg, en: en as Dictionary };

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale] ?? dictionaries.bg;
}
