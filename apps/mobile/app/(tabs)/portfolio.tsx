import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Modal,
  TextInput,
} from "react-native";
import { useTranslation } from "../../src/i18n";
import {
  useHoldingsQuery,
  useAlertsQuery,
  useCreateAlertMutation,
  useDeleteAlertMutation,
  useCompoundSimulatorMutation,
} from "../../src/api/hooks";

export default function PortfolioScreen() {
  const { t } = useTranslation();
  const { data: holdingsData, isLoading, refetch } = useHoldingsQuery();
  const { data: alertsData } = useAlertsQuery();
  const createAlertMutation = useCreateAlertMutation();
  const deleteAlertMutation = useDeleteAlertMutation();
  const simMutation = useCompoundSimulatorMutation();
  const [refreshing, setRefreshing] = useState(false);
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [showSimModal, setShowSimModal] = useState(false);

  // Alert form
  const [alertTicker, setAlertTicker] = useState("");
  const [alertPrice, setAlertPrice] = useState("");
  const [alertDir, setAlertDir] = useState<"above" | "below">("above");

  // Sim form
  const [simInitial, setSimInitial] = useState("");
  const [simMonthly, setSimMonthly] = useState("");
  const [simRate, setSimRate] = useState("");
  const [simYears, setSimYears] = useState("");
  const [simResult, setSimResult] = useState<{
    future_value: number;
    total_contributions: number;
    total_interest: number;
  } | null>(null);

  const onRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  const handleCreateAlert = async () => {
    if (!alertTicker.trim() || !alertPrice.trim()) return;
    try {
      await createAlertMutation.mutateAsync({
        ticker: alertTicker.trim().toUpperCase(),
        target_price: parseFloat(alertPrice),
        direction: alertDir,
      });
      setShowAlertModal(false);
      setAlertTicker("");
      setAlertPrice("");
    } catch {
      // handled
    }
  };

  const handleSimulate = async () => {
    try {
      const result = await simMutation.mutateAsync({
        initial: parseFloat(simInitial) || 0,
        monthly: parseFloat(simMonthly) || 0,
        rate_pct: parseFloat(simRate) || 0,
        years: parseInt(simYears) || 0,
      });
      setSimResult(result);
    } catch {
      // handled
    }
  };

  const holdings = holdingsData?.holdings ?? [];
  const alerts = alertsData?.alerts ?? [];

  return (
    <ScrollView
      className="flex-1 bg-surface-light dark:bg-surface-dark"
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <View className="px-5 pt-6">
        {/* Portfolio Header */}
        <View className="bg-primary-500 rounded-2xl p-5 mb-6">
          <Text className="text-white/80 text-sm">{t("portfolio.totalValue")}</Text>
          <Text className="text-white text-3xl font-bold mt-1">
            {holdingsData?.total_value ?? "0"} {holdingsData?.currency ?? "EUR"}
          </Text>
          {holdingsData?.total_gain_pct != null && (
            <View className="flex-row items-center mt-2">
              <Text
                className={`text-white font-semibold ${
                  holdingsData.total_gain_pct >= 0 ? "" : "text-red-200"
                }`}
              >
                {holdingsData.total_gain_pct >= 0 ? "+" : ""}
                {holdingsData.total_gain_pct.toFixed(2)}%
              </Text>
              <Text className="text-white/70 ml-2">
                {t("portfolio.totalReturn")}
              </Text>
            </View>
          )}
        </View>

        {/* Holdings */}
        <View className="flex-row justify-between items-center mb-3">
          <Text className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
            {t("portfolio.holdings")}
          </Text>
        </View>

        {isLoading ? (
          <ActivityIndicator className="my-4" />
        ) : holdings.length > 0 ? (
          holdings.map((holding: any) => (
            <View
              key={holding.id}
              className="bg-card-light dark:bg-card-dark rounded-xl p-4 mb-3"
            >
              <View className="flex-row justify-between items-start">
                <View>
                  <Text className="font-semibold text-lg text-text-primary-light dark:text-text-primary-dark">
                    {holding.ticker}
                  </Text>
                  <Text className="text-text-secondary-light dark:text-text-secondary-dark text-sm">
                    {holding.name}
                  </Text>
                  <Text className="text-text-muted-light dark:text-text-muted-dark text-xs mt-1">
                    {holding.shares} {t("portfolio.shares")} · {holding.asset_type}
                  </Text>
                </View>
                <View className="items-end">
                  <Text className="font-bold text-text-primary-light dark:text-text-primary-dark">
                    {holding.market_value ?? "—"} {holding.currency}
                  </Text>
                  {holding.unrealized_gain_pct != null && (
                    <Text
                      className={`text-sm font-medium ${
                        holding.unrealized_gain_pct >= 0
                          ? "text-green-600 dark:text-green-400"
                          : "text-red-600 dark:text-red-400"
                      }`}
                    >
                      {holding.unrealized_gain_pct >= 0 ? "+" : ""}
                      {holding.unrealized_gain_pct.toFixed(2)}%
                    </Text>
                  )}
                  <Text className="text-text-muted-light dark:text-text-muted-dark text-xs mt-1">
                    {t("portfolio.price")}: {holding.current_price ?? "—"}{" "}
                    {holding.currency}
                  </Text>
                </View>
              </View>
            </View>
          ))
        ) : (
          <View className="bg-card-light dark:bg-card-dark rounded-xl p-6 items-center mb-4">
            <Text className="text-text-muted-light dark:text-text-muted-dark">
              {t("portfolio.noHoldings")}
            </Text>
            <Text className="text-text-muted-light dark:text-text-muted-dark text-sm mt-1 text-center">
              {t("portfolio.noHoldingsDesc")}
            </Text>
          </View>
        )}

        {/* Alerts */}
        <View className="flex-row justify-between items-center mb-3 mt-4">
          <Text className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
            {t("portfolio.alerts")}
          </Text>
          <TouchableOpacity
            className="bg-primary-500/10 dark:bg-primary-500/20 px-3 py-1.5 rounded-lg"
            onPress={() => setShowAlertModal(true)}
          >
            <Text className="text-primary-600 dark:text-primary-400 text-sm font-medium">
              {t("portfolio.addAlert")}
            </Text>
          </TouchableOpacity>
        </View>

        {alerts.length > 0 ? (
          alerts.map((alert: any) => (
            <View
              key={alert.id}
              className="bg-card-light dark:bg-card-dark rounded-xl p-3 mb-2 flex-row justify-between items-center"
            >
              <View>
                <Text className="font-semibold text-text-primary-light dark:text-text-primary-dark">
                  {alert.ticker}{" "}
                  <Text className="text-text-secondary-light dark:text-text-secondary-dark font-normal">
                    {alert.direction} {alert.target_price}
                  </Text>
                </Text>
                <Text className="text-text-muted-light dark:text-text-muted-dark text-xs">
                  {alert.is_active ? "Active" : "Triggered"}
                </Text>
              </View>
              <TouchableOpacity
                onPress={() => deleteAlertMutation.mutate(alert.id)}
              >
                <Text className="text-red-500 text-sm">✕</Text>
              </TouchableOpacity>
            </View>
          ))
        ) : (
          <Text className="text-text-muted-light dark:text-text-muted-dark text-sm mb-4">
            {t("portfolio.noAlerts")}
          </Text>
        )}

        {/* Compound Simulator */}
        <View className="mt-4 mb-4">
          <TouchableOpacity
            className="bg-card-light dark:bg-card-dark rounded-xl p-4"
            onPress={() => setShowSimModal(true)}
          >
            <Text className="font-semibold text-text-primary-light dark:text-text-primary-dark">
              {t("portfolio.simulator")}
            </Text>
            <Text className="text-text-secondary-light dark:text-text-secondary-dark text-sm mt-1">
              {t("portfolio.simResult")}
              {simResult ? `: ${simResult.future_value.toFixed(2)} €` : ""}
            </Text>
          </TouchableOpacity>
        </View>

        <View className="h-8" />
      </View>

      {/* Alert Modal */}
      <Modal visible={showAlertModal} transparent animationType="slide">
        <View className="flex-1 justify-center bg-black/50 px-5">
          <View className="bg-white dark:bg-slate-800 rounded-2xl p-5">
            <Text className="text-lg font-bold text-text-primary-light dark:text-text-primary-dark mb-4">
              {t("portfolio.alertPrice")}
            </Text>

            <Text className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-1">
              {t("portfolio.ticker")}
            </Text>
            <TextInput
              className="bg-gray-100 dark:bg-gray-700 rounded-lg px-4 py-3 mb-3 text-text-primary-light dark:text-text-primary-dark"
              placeholder="AAPL"
              placeholderTextColor="#94A3B8"
              autoCapitalize="characters"
              value={alertTicker}
              onChangeText={setAlertTicker}
            />

            <Text className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-1">
              {t("portfolio.alertTarget")}
            </Text>
            <TextInput
              className="bg-gray-100 dark:bg-gray-700 rounded-lg px-4 py-3 mb-3 text-text-primary-light dark:text-text-primary-dark"
              placeholder="150.00"
              placeholderTextColor="#94A3B8"
              keyboardType="decimal-pad"
              value={alertPrice}
              onChangeText={setAlertPrice}
            />

            <View className="flex-row mb-4">
              <TouchableOpacity
                className={`flex-1 py-2 rounded-lg mr-2 ${
                  alertDir === "above" ? "bg-green-500" : "bg-gray-200 dark:bg-gray-600"
                }`}
                onPress={() => setAlertDir("above")}
              >
                <Text
                  className={`text-center font-medium ${
                    alertDir === "above" ? "text-white" : "text-text-secondary-light dark:text-text-secondary-dark"
                  }`}
                >
                  {t("portfolio.alertAbove")}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                className={`flex-1 py-2 rounded-lg ml-2 ${
                  alertDir === "below" ? "bg-red-500" : "bg-gray-200 dark:bg-gray-600"
                }`}
                onPress={() => setAlertDir("below")}
              >
                <Text
                  className={`text-center font-medium ${
                    alertDir === "below" ? "text-white" : "text-text-secondary-light dark:text-text-secondary-dark"
                  }`}
                >
                  {t("portfolio.alertBelow")}
                </Text>
              </TouchableOpacity>
            </View>

            <View className="flex-row">
              <TouchableOpacity
                className="flex-1 py-3 rounded-lg mr-2 border border-gray-300 dark:border-gray-600"
                onPress={() => setShowAlertModal(false)}
              >
                <Text className="text-center text-text-primary-light dark:text-text-primary-dark">
                  {t("common.cancel")}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                className="flex-1 py-3 rounded-lg ml-2 bg-primary-500"
                onPress={handleCreateAlert}
                disabled={createAlertMutation.isPending}
              >
                {createAlertMutation.isPending ? (
                  <ActivityIndicator color="white" />
                ) : (
                  <Text className="text-center text-white font-semibold">
                    {t("common.save")}
                  </Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Simulator Modal */}
      <Modal visible={showSimModal} transparent animationType="slide">
        <View className="flex-1 justify-center bg-black/50 px-5">
          <View className="bg-white dark:bg-slate-800 rounded-2xl p-5">
            <Text className="text-lg font-bold text-text-primary-light dark:text-text-primary-dark mb-4">
              {t("portfolio.simulator")}
            </Text>

            {[
              { label: t("portfolio.simInitial"), value: simInitial, setter: setSimInitial },
              { label: t("portfolio.simMonthly"), value: simMonthly, setter: setSimMonthly },
              { label: t("portfolio.simRate"), value: simRate, setter: setSimRate },
              { label: t("portfolio.simYears"), value: simYears, setter: setSimYears },
            ].map((field, i) => (
              <View key={i} className="mb-3">
                <Text className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-1">
                  {field.label}
                </Text>
                <TextInput
                  className="bg-gray-100 dark:bg-gray-700 rounded-lg px-4 py-2.5 text-text-primary-light dark:text-text-primary-dark"
                  keyboardType="decimal-pad"
                  value={field.value}
                  onChangeText={field.setter}
                />
              </View>
            ))}

            {simResult && (
              <View className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3 mb-4">
                <Text className="text-text-primary-light dark:text-text-primary-dark font-semibold">
                  {t("portfolio.simResult")}: {simResult.future_value.toFixed(2)} €
                </Text>
                <Text className="text-text-secondary-light dark:text-text-secondary-dark text-sm">
                  {t("portfolio.simContributions")}:{" "}
                  {simResult.total_contributions.toFixed(2)} €
                </Text>
                <Text className="text-green-600 dark:text-green-400 text-sm">
                  {t("portfolio.simInterest")}: {simResult.total_interest.toFixed(2)} €
                </Text>
              </View>
            )}

            <View className="flex-row">
              <TouchableOpacity
                className="flex-1 py-3 rounded-lg mr-2 border border-gray-300 dark:border-gray-600"
                onPress={() => setShowSimModal(false)}
              >
                <Text className="text-center text-text-primary-light dark:text-text-primary-dark">
                  {t("common.cancel")}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                className="flex-1 py-3 rounded-lg ml-2 bg-primary-500"
                onPress={handleSimulate}
                disabled={simMutation.isPending}
              >
                {simMutation.isPending ? (
                  <ActivityIndicator color="white" />
                ) : (
                  <Text className="text-center text-white font-semibold">
                    {t("common.confirm")}
                  </Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}
