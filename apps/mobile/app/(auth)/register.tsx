import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import { useTranslation } from "../../src/i18n";
import { useAuth } from "../../src/hooks/useAuth";

export default function RegisterScreen() {
  const { t } = useTranslation();
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    setError("");
    if (!email.trim() || !password.trim()) {
      setError("Please fill all fields");
      return;
    }
    if (password.length < 8) {
      setError(t("auth.passwordMinLength"));
      return;
    }
    if (password !== confirm) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    setLoading(true);
    try {
      await register({ email: email.trim(), password });
    } catch (e: unknown) {
      const msg = (e as { detail?: string })?.detail ?? t("auth.registerError");
      setError(msg);
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      className="flex-1 bg-surface-light dark:bg-surface-dark"
    >
      <ScrollView
        contentContainerStyle={{ flexGrow: 1, justifyContent: "center" }}
        className="px-8"
      >
        <View className="items-center mb-10">
          <Text className="text-4xl font-bold text-primary-500 mb-2">Stonks</Text>
          <Text className="text-lg text-text-secondary-light dark:text-text-secondary-dark">
            {t("auth.register")}
          </Text>
        </View>

        {error ? (
          <View className="bg-red-100 dark:bg-red-900/30 rounded-lg p-3 mb-4">
            <Text className="text-red-600 dark:text-red-400 text-center">{error}</Text>
          </View>
        ) : null}

        <View className="mb-4">
          <Text className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">
            {t("auth.email")}
          </Text>
          <TextInput
            className="bg-card-light dark:bg-card-dark border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3 text-text-primary-light dark:text-text-primary-dark"
            placeholder="email@example.com"
            placeholderTextColor="#94A3B8"
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
            value={email}
            onChangeText={setEmail}
          />
        </View>

        <View className="mb-4">
          <Text className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">
            {t("auth.password")}
          </Text>
          <TextInput
            className="bg-card-light dark:bg-card-dark border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3 text-text-primary-light dark:text-text-primary-dark"
            placeholder="••••••••"
            placeholderTextColor="#94A3B8"
            secureTextEntry
            autoComplete="new-password"
            value={password}
            onChangeText={setPassword}
          />
        </View>

        <View className="mb-6">
          <Text className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">
            {t("auth.confirmPassword")}
          </Text>
          <TextInput
            className="bg-card-light dark:bg-card-dark border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3 text-text-primary-light dark:text-text-primary-dark"
            placeholder="••••••••"
            placeholderTextColor="#94A3B8"
            secureTextEntry
            autoComplete="new-password"
            value={confirm}
            onChangeText={setConfirm}
          />
        </View>

        <TouchableOpacity
          className="bg-primary-500 rounded-lg py-3.5 items-center mb-4"
          onPress={handleRegister}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="white" />
          ) : (
            <Text className="text-white font-semibold text-base">
              {t("auth.registerButton")}
            </Text>
          )}
        </TouchableOpacity>

        <View className="flex-row justify-center">
          <Text className="text-text-muted-light dark:text-text-muted-dark">
            {t("auth.hasAccount")}{" "}
          </Text>
          <TouchableOpacity onPress={() => router.back()}>
            <Text className="text-primary-500 font-medium">
              {t("auth.loginLink")}
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
