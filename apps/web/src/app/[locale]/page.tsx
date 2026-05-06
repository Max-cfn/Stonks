import { getTranslations } from "next-intl/server";
import Link from "next/link";

export default async function LocaleHomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "nav" });

  return (
    <div className="flex flex-col items-center justify-center py-24">
      <h1 className="text-4xl font-bold tracking-tight">Stonks</h1>
      <p className="mt-4 text-lg text-muted-foreground">
        Personal Finance Platform — powered by AI agents
      </p>
      <Link
        href={`/${locale}/dashboard`}
        className="mt-8 inline-flex items-center justify-center rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
      >
        {t("dashboard")}
      </Link>
    </div>
  );
}
