import React from "react";
import { View, Text, ScrollView, RefreshControl } from "react-native";
import { useTranslation } from "../../src/i18n";
import { useUserQuery, useAccountsQuery, useHoldingsQuery } from "../../src/api/hooks";
import { useAuth } from "../../src/hooks/useAuth";

export default function DashboardScreen() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const {
    data: userData,
    isLoading: userLoading,
    refetch: refetchUser,
  } = useUserQuery();
  const { data: accountsData, refetch: refetchAccounts } = useAccountsQuery();
  const { data: holdingsData, refetch: refetchHoldings } = useHoldingsQuery();

  const [refreshing, setRefreshing] = React.useState(false);
  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([refetchUser(), refetchAccounts(), refetchHoldings()]);
    setRefreshing(false);
  };

  const firstName = user?.email?.split("@")[0] ?? "Investor";

  return (
    <ScrollView
      className="flex-1 bg-surface-light dark:bg-surface-dark"
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <View className="px-5 pt-6">
        {/* Welcome */}
        <View className="mb-6">
          <Text className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
            {t("dashboard.welcome")}, {firstName}
          </Text>
          <Text className="text-text-secondary-light dark:text-text-secondary-dark mt-1">
            {userData?.email ?? user?.email}
          </Text>
        </View>

        {/* Quick Stats Grid */}
        <View className="flex-row flex-wrap -mx-2 mb-6">
          <StatCard
            title={t("dashboard.portfolioValue")}
            value={holdingsData?.total_value ? `${holdingsData.total_value} €` : "—"}
            color="primary"
          />
          <StatCard
            title={t("dashboard.monthlyIncome")}
            value="—"
            color="green"
          />
          <StatCard
            title={t("dashboard.monthlyExpenses")}
            value="—"
            color="red"
          />
          <StatCard
            title={t("dashboard.savings")}
            value="—"
            color="yellow"
          />
        </View>

        {/* Connected Accounts */}
        <Text className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark mb-3">
          {t("dashboard.recentTransactions")}
        </Text>
        {accountsData?.accounts && accountsData.accounts.length > 0 ? (
          accountsData.accounts.map((acc) => (
            <View
              key={acc.id}
              className="bg-card-light dark:bg-card-dark rounded-xl p-4 mb-2"
            >
              <Text className="font-semibold text-text-primary-light dark:text-text-primary-dark">
                {acc.account_name}
              </Text>
              <Text className="text-text-secondary-light dark:text-text-secondary-dark text-sm">
                {acc.current_balance ?? "0"} {acc.currency}
              </Text>
            </View>
          ))
        ) : (
          <View className="bg-card-light dark:bg-card-dark rounded-xl p-6 items-center">
            <Text className="text-text-muted-light dark:text-text-muted-dark">
              {t("cashflow.noAccounts")}
            </Text>
            <Text className="text-text-muted-light dark:text-text-muted-dark text-sm mt-1 text-center">
              {t("cashflow.noAccountsDesc")}
            </Text>
          </View>
        )}

        <View className="h-8" />
      </View>
    </ScrollView>
  );
}

function StatCard({
  title,
  value,
  color,
}: {
  title: string;
  value: string;
  color: "primary" | "green" | "red" | "yellow";
}) {
  const colorMap = {
    primary: "bg-primary-500/10 dark:bg-primary-500/20",
    green: "bg-green-100 dark:bg-green-900/20",
    red: "bg-red-100 dark:bg-red-900/20",
    yellow: "bg-yellow-100 dark:bg-yellow-900/20",
  };
  const textColorMap = {
    primary: "text-primary-600 dark:text-primary-400",
    green: "text-green-600 dark:text-green-400",
    red: "text-red-600 dark:text-red-400",
    yellow: "text-yellow-600 dark:text-yellow-400",
  };

  return (
    <View className="w-1/2 px-2 mb-3">
      <View className={`${colorMap[color]} rounded-xl p-4`}>
        <Text className="text-text-secondary-light dark:text-text-secondary-dark text-xs mb-1">
          {title}
        </Text>
        <Text className={`text-lg font-bold ${textColorMap[color]}`}>{value}</Text>
      </View>
    </View>
  );
}
