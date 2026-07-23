// Локал-осъзнато форматиране на числа. Досега графиките бяха твърдо "bg-BG", което
// форматираше английския изглед грешно (интервал вместо запетая за хиляди).

const LOCALES: Record<string, string> = { bg: "bg-BG", en: "en-GB" };

export function localeFor(lang: string): string {
  return LOCALES[lang] ?? "bg-BG";
}

export function numberFormat(lang: string): Intl.NumberFormat {
  return new Intl.NumberFormat(localeFor(lang), { maximumFractionDigits: 2 });
}
