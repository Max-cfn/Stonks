import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import { Platform, NativeModules } from "react-native";
import { en, fr, defaultNS } from "./resources";

const getDeviceLang = (): "en" | "fr" => {
  try {
    const locale =
      Platform.OS === "ios"
        ? NativeModules.SettingsManager?.settings?.AppleLocale ??
          NativeModules.SettingsManager?.settings?.AppleLanguages?.[0]
        : NativeModules.I18nManager?.localeIdentifier;
    if (locale?.startsWith("fr")) return "fr";
  } catch {
    // fallback
  }
  return "en";
};

i18next.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    fr: { translation: fr },
  },
  lng: getDeviceLang(),
  fallbackLng: "en",
  defaultNS,
  interpolation: { escapeValue: false },
  compatibilityJSON: "v4",
});

export default i18next;
export { useTranslation } from "react-i18next";
