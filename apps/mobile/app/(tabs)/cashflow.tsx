import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { useTranslation } from "../../src/i18n";
import {
  useAccountsQuery,
  useConnectBankMutation,
  useSyncAccountMutation,
  useCashflowSummaryQuery,
} from "../../src/api/hooks";
import type { AccountResponse } from "../../src/api/types";

export default function CashflowScreen() {
  const { t } = useTranslation();
  const {
    data: accountsData,
    isLoading: accountsLoading,
    refetch: refetchAccounts,
  } = useAccountsQuery();
  const { data: summaryData } = useCashflowSummaryQuery();
  const connectMutation = useConnectBankMutation();
  const syncMutation = useSyncAccountMutation();
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = async () => {
    setRefreshing(true);
    await refetchAccounts();
    setRefreshing(false);
  };

  const handleConnect = async () => {
    try {
      const result = await connectMutation.mutateAsync();
      alert(`Open this URL to connect:\n${result.authorization_url}`);
    } catch {
      // handled by mutation
    }
  };

  const handleSync = (accountId: string) => {
    syncMutation.mutate(accountId);
  };

  return (
    <ScrollView
      className="flex-1 bg-surface-light dark:bg-surface-dark"
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <View className="px-5 pt-6">
        {/* Summary Card */}
        {summaryData ? (
          <View className="bg-primary-500 rounded-2xl p-5 mb-6">
            <Text className="text-white/80 text-sm mb-1">{t("cashflow.summary")}</Text>
            <View className="flex-row justify-between mt-2">
              <View>
                <Text className="text-white/70 text-xs">{t("cashflow.totalIncome")}</Text>
                <Text className="text-white text-xl font-bold">
                  {summaryData.total_income} {summaryData.currency}
                </Text>
              </View>
              <View>
                <Text className="text-white/70 text-xs">{t("cashflow.totalExpenses")}</Text>
                <Text className="text-white text-xl font-bold">
                  {summaryData.total_expenses} {summaryData.currency}
                </Text>
              </View>
            </View>
            <View className="mt-2 pt-2 border-t border-white/20">
              <Text className="text-white font-bold text-lg">
                {t("cashflow.netCashflow")}: {summaryData.net} {summaryData.currency}
              </Text>
            </View>
          </View>
        ) : null}

        {/* Accounts */}
        <View className="flex-row justify-between items-center mb-3">
          <Text className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
            {t("cashflow.accounts")}
          </Text>
          <TouchableOpacity
            className="bg-primary-500 px-4 py-2 rounded-lg"
            onPress={handleConnect}
            disabled={connectMutation.isPending}
          >
            {connectMutation.isPending ? (
              <ActivityIndicator size="small" color="white" />
            ) : (
              <Text className="text-white font-medium text-sm">
                {t("cashflow.connectBank")}
              </Text>
            )}
          </TouchableOpacity>
        </View>

        {accountsLoading ? (
          <ActivityIndicator className="my-4" />
        ) : accountsData?.accounts && accountsData.accounts.length > 0 ? (
          accountsData.accounts.map((account: AccountResponse) => (
            <View
              key={account.id}
              className="bg-card-light dark:bg-card-dark rounded-xl p-4 mb-3"
            >
              <View className="flex-row justify-between items-start">
                <View>
                  <Text className="font-semibold text-text-primary-light dark:text-text-primary-dark">
                    {account.account_name}
                  </Text>
                  <Text className="text-text-secondary-light dark:text-text-secondary-dark text-sm">
                    {account.iban}
                  </Text>
                  <Text className="text-text-muted-light dark:text-text-muted-dark text-xs mt-1">
                    {account.account_type} · {account.status}
                  </Text>
                </View>
                <View className="items-end">
                  <Text className="font-bold text-lg text-text-primary-light dark:text-text-primary-dark">
                    {account.current_balance ?? "—"} {account.currency}
                  </Text>
                  <TouchableOpacity
                    className="bg-primary-500/10 dark:bg-primary-500/20 rounded-lg px-3 py-1.5 mt-2"
                    onPress={() => handleSync(account.id)}
                    disabled={syncMutation.isPending}
                  >
                    {syncMutation.isPending ? (
                      <ActivityIndicator size="small" color="#3B82F6" />
                    ) : (
                      <Text className="text-primary-600 dark:text-primary-400 text-xs font-medium">
                        {t("cashflow.syncNow")}
                      </Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
              {account.last_synced_at ? (
                <Text className="text-text-muted-light dark:text-text-muted-dark text-xs mt-2">
                  {t("cashflow.lastSync")}:{" "}
                  {new Date(account.last_synced_at).toLocaleString()}
                </Text>
              ) : null}
            </View>
          ))
        ) : (
          <View className="bg-card-light dark:bg-card-dark rounded-xl p-6 items-center">
            <Text className="text-text-muted-light dark:text-text-muted-dark text-center">
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
