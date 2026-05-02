import React from "react";
import { Tabs } from "expo-router";
import { useColorScheme } from "nativewind";

export default function TabsLayout() {
  const { colorScheme } = useColorScheme();
  const isDark = colorScheme === "dark";
  const activeColor = "#3B82F6";
  const inactiveColor = isDark ? "#64748B" : "#94A3B8";

  return (
    <Tabs
      screenOptions={{
        headerStyle: {
          backgroundColor: isDark ? "#0F172A" : "#FFFFFF",
        },
        headerTintColor: isDark ? "#F1F5F9" : "#0F172A",
        tabBarStyle: {
          backgroundColor: isDark ? "#0F172A" : "#FFFFFF",
          borderTopColor: isDark ? "#1E293B" : "#E2E8F0",
        },
        tabBarActiveTintColor: activeColor,
        tabBarInactiveTintColor: inactiveColor,
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          headerTitle: "Stonks",
          title: "Dashboard",
          tabBarIcon: ({ color }) => (
            <TabIcon emoji="🏠" accessibilityLabel="Dashboard" />
          ),
        }}
      />
      <Tabs.Screen
        name="cashflow"
        options={{
          title: "Cashflow",
          tabBarIcon: ({ color }) => (
            <TabIcon emoji="💰" accessibilityLabel="Cashflow" />
          ),
        }}
      />
      <Tabs.Screen
        name="portfolio"
        options={{
          title: "Portfolio",
          tabBarIcon: ({ color }) => (
            <TabIcon emoji="📈" accessibilityLabel="Portfolio" />
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Settings",
          tabBarIcon: ({ color }) => (
            <TabIcon emoji="⚙️" accessibilityLabel="Settings" />
          ),
        }}
      />
    </Tabs>
  );
}

import { Text } from "react-native";

function TabIcon({ emoji, accessibilityLabel }: { emoji: string; accessibilityLabel: string }) {
  return (
    <Text style={{ fontSize: 22 }} accessibilityLabel={accessibilityLabel}>
      {emoji}
    </Text>
  );
}
