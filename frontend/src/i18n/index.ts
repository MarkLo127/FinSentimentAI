import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import zhTW from './zh-TW.json'

// Map every plausible Chinese variant the browser might report to the
// zh-TW resource bundle so the lookup never falls through to keys.
const zhResource = { translation: zhTW }
const enResource = { translation: en }

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: enResource,
      'en-US': enResource,
      'zh-TW': zhResource,
      zh: zhResource,
      'zh-Hant': zhResource,
      'zh-Hant-TW': zhResource,
      'zh-Hans': zhResource,
      'zh-CN': zhResource,
      'zh-HK': zhResource,
    },
    fallbackLng: 'zh-TW',
    supportedLngs: [
      'en',
      'en-US',
      'zh-TW',
      'zh',
      'zh-Hant',
      'zh-Hant-TW',
      'zh-Hans',
      'zh-CN',
      'zh-HK',
    ],
    load: 'currentOnly',
    interpolation: { escapeValue: false },
    react: { useSuspense: false },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'finsentiment.lang',
      caches: ['localStorage'],
    },
  })

export default i18n
