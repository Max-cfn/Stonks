import { useEffect, useRef, useState } from "react";
import * as Notifications from "expo-notifications";
import { useRegisterPushTokenMutation } from "../api/hooks";
import { Platform } from "react-native";

// Configure notification handler
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

// Handle notification tap (opens portfolio tab)
// This is configured in the notification response listener

export function usePushNotifications() {
  const [expoPushToken, setExpoPushToken] = useState<string | null>(null);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const registerToken = useRegisterPushTokenMutation();
  const notificationListener = useRef<Notifications.Subscription>();
  const responseListener = useRef<Notifications.Subscription>();

  useEffect(() => {
    async function register() {
      // Check permissions
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;

      if (existingStatus !== "granted") {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }

      if (finalStatus !== "granted") {
        setPermissionGranted(false);
        return;
      }

      setPermissionGranted(true);

      // Get Expo push token
      try {
        const tokenData = await Notifications.getExpoPushTokenAsync({
          projectId: "TODO-add-project-id", // Will be configured per env
        });
        setExpoPushToken(tokenData.data);

        // Register with backend
        await registerToken.mutateAsync(tokenData.data);
      } catch (err) {
        console.warn("Failed to get push token:", err);
      }

      // Android specific channel
      if (Platform.OS === "android") {
        await Notifications.setNotificationChannelAsync("price-alerts", {
          name: "Price Alerts",
          importance: Notifications.AndroidImportance.HIGH,
          vibrationPattern: [0, 250, 250, 250],
          lightColor: "#3B82F6",
          sound: "default",
        });
      }
    }

    // Listen for incoming notifications
    notificationListener.current =
      Notifications.addNotificationReceivedListener((notification) => {
        // Handle incoming notification while app is foregrounded
        console.log("Notification received:", notification);
      });

    // Listen for notification tap
    responseListener.current =
      Notifications.addNotificationResponseReceivedListener((response) => {
        // The notification payload should contain a deep link
        const data = response.notification.request.content.data;
        if (data?.screen === "portfolio") {
          // Navigation is handled by expo-router
          // The deep link could be: stonks://portfolio
        }
      });

    register();

    return () => {
      if (notificationListener.current) {
        Notifications.removeNotificationSubscription(notificationListener.current);
      }
      if (responseListener.current) {
        Notifications.removeNotificationSubscription(responseListener.current);
      }
    };
  }, []);

  return { expoPushToken, permissionGranted };
}

// Test function — can be called from dev tools
export async function sendTestPush() {
  await Notifications.scheduleNotificationAsync({
    content: {
      title: "🔔 Price Alert",
      body: "AAPL reached $150.00 (above target)",
      data: { screen: "portfolio", ticker: "AAPL" },
      sound: "default",
    },
    trigger: null, // immediate
  });
}
