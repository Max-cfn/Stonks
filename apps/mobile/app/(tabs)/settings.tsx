import React from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
} from "react-native";
import { useTranslation } from "../../src/i18n";
import { useAuth } from "../../src/hooks/useAuth";
import { useColorScheme } from "nativewind";

export default function SettingsScreen() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const { colorScheme, setColorScheme } = useColorScheme();

  const handleLogout = () => {
    Alert.alert(
      t("auth.logout"),
      t("auth.logoutConfirm"),
      [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("auth.logout"),
          style: "destructive",
          onPress: logout,
        },
      ],
    );
  };

  const toggleLang = () => {
    const next = i18n.language === "fr" ? "en" : "fr";
    i18n.changeLanguage(next);
  };

  const cycleTheme = () => {
    if (colorScheme === "light") {
      setColorScheme("dark");
    } else if (colorScheme === "dark") {
      setColorScheme("system");
    } else {
      setColorScheme("light");
    }
  };

  const themeLabel = () => {
    switch (colorScheme) {
      case "light":
        return t("settings.themeLight");
      case "dark":
        return t("settings.themeDark");
      default:
        return t("settings.themeSystem");
    }
  };

  return (
    <ScrollView className="flex-1 bg-surface-light dark:bg-surface-dark">
      <View className="px-5 pt-6">
        {/* Profile */}
        <Text className="text-xs font-semibold text-text-muted-light dark:text-text-muted-dark uppercase tracking-wide mb-2">
          {t("settings.profile")}
        </Text>
        <View className="bg-card-light dark:bg-card-dark rounded-xl p-4 mb-6">
          <Text className="font-semibold text-text-primary-light dark:text-text-primary-dark">
            {user?.email ?? "—"}
          </Text>
          <Text className="text-text-secondary-light dark:text-text-secondary-dark text-sm mt-1">
            {t("settings.memberSince")}:{" "}
            {user?.created_at
              ? new Date(user.created_at).toLocaleDateString()
              : "—"}
          </Text>
        </View>

        {/* Appearance */}
        <Text className="text-xs font-semibold text-text-muted-light dark:text-text-muted-dark uppercase tracking-wide mb-2">
          {t("settings.appearance")}
        </Text>
        <View className="bg-card-light dark:bg-card-dark rounded-xl mb-6">
          <TouchableOpacity
            className="flex-row justify-between items-center px-4 py-3.5 border-b border-gray-100 dark:border-gray-700"
            onPress={cycleTheme}
          >
            <Text className="text-text-primary-light dark:text-text-primary-dark">
              {t("settings.theme")}
            </Text>
            <Text className="text-text-secondary-light dark:text-text-secondary-dark">
              {themeLabel()}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            className="flex-row justify-between items-center px-4 py-3.5"
            onPress={toggleLang}
          >
            <Text className="text-text-primary-light dark:text-text-primary-dark">
              {t("settings.language")}
            </Text>
            <Text className="text-text-secondary-light dark:text-text-secondary-dark">
              {i18n.language === "fr" ? "🇫🇷 Français" : "🇬🇧 English"}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Notifications */}
        <Text className="text-xs font-semibold text-text-muted-light dark:text-text-muted-dark uppercase tracking-wide mb-2">
          {t("settings.notifications")}
        </Text>
        <View className="bg-card-light dark:bg-card-dark rounded-xl mb-6">
          <View className="flex-row justify-between items-center px-4 py-3.5 border-b border-gray-100 dark:border-gray-700">
            <View className="flex-1 mr-4">
              <Text className="text-text-primary-light dark:text-text-primary-dark">
                {t("settings.pushEnabled")}
              </Text>
              <Text className="text-text-secondary-light dark:text-text-secondary-dark text-sm">
                {t("settings.pushEnabledDesc")}
              </Text>
            </View>
            <Switch value={true} />
          </View>
          <View className="flex-row justify-between items-center px-4 py-3.5">
            <View className="flex-1 mr-4">
              <Text className="text-text-primary-light dark:text-text-primary-dark">
                {t("settings.priceAlerts")}
              </Text>
              <Text className="text-text-secondary-light dark:text-text-secondary-dark text-sm">
                {t("settings.priceAlertsDesc")}
              </Text>
            </View>
            <Switch value={true} />
          </View>
        </View>

        {/* About */}
        <Text className="text-xs font-semibold text-text-muted-light dark:text-text-muted-dark uppercase tracking-wide mb-2">
          {t("settings.about")}
        </Text>
        <View className="bg-card-light dark:bg-card-dark rounded-xl p-4 mb-6">
          <Text className="text-text-primary-light dark:text-text-primary-dark">
            Stonks
          </Text>
          <Text className="text-text-secondary-light dark:text-text-secondary-dark text-sm">
            {t("settings.version")} 0.1.0
          </Text>
        </View>

        {/* Logout */}
        <TouchableOpacity
          className="bg-red-50 dark:bg-red-900/20 rounded-xl p-4 items-center mb-10"
          onPress={handleLogout}
        >
          <Text className="text-red-600 dark:text-red-400 font-semibold">
            {t("settings.logout")}
          </Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}
