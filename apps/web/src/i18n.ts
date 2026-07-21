import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

export const LOCALE_STORAGE_KEY = 'pcb-cdso:locale:v1'

const resources = {
  'zh-CN': {
    translation: {
      eyebrow: 'PCB 冷源专家系统 · v0.6',
      title: 'PCB 工厂冷源需求计算与仿真系统',
      subtitle: '以固定生产工艺为起点，建立可审计的冷量需求基线与逐时动态预测。',
      processDriven: '工艺驱动',
      processDrivenDetail: '区域、工序与环境标准形成完整约束链',
      simulation: '动态仿真',
      simulationDetail: '天气与生产负荷共同驱动逐时预测',
      traceable: '全程可追溯',
      traceableDetail: '版本、输入、计算与结果均保留审计依据',
      signIn: '登录工作台',
      welcome: '进入工程计算与仿真环境',
      email: '邮箱',
      emailPlaceholder: 'engineer@factory.com',
      password: '密码',
      passwordPlaceholder: '请输入密码',
      login: '登录',
      pending: '身份认证将在 M1 阶段启用',
      language: 'English',
      dark: '深色模式',
      light: '浅色模式',
      foundation: 'M0 基础设施已就绪',
    },
  },
  'en-US': {
    translation: {
      eyebrow: 'PCB Cooling Expert System · v0.6',
      title: 'PCB Factory Cooling Demand & Simulation',
      subtitle: 'Build an auditable cooling-demand baseline and hourly forecast from fixed production processes.',
      processDriven: 'Process driven',
      processDrivenDetail: 'Zones, processes and environmental standards form one constraint chain',
      simulation: 'Dynamic simulation',
      simulationDetail: 'Weather and production load drive hourly forecasts together',
      traceable: 'Fully traceable',
      traceableDetail: 'Versions, inputs, calculations and results retain an audit trail',
      signIn: 'Sign in to workspace',
      welcome: 'Enter the engineering calculation environment',
      email: 'Email',
      emailPlaceholder: 'engineer@factory.com',
      password: 'Password',
      passwordPlaceholder: 'Enter password',
      login: 'Sign in',
      pending: 'Authentication will be enabled in milestone M1',
      language: '中文',
      dark: 'Dark mode',
      light: 'Light mode',
      foundation: 'M0 foundation ready',
    },
  },
} as const

function storedLocale(): 'zh-CN' | 'en-US' {
  return localStorage.getItem(LOCALE_STORAGE_KEY) === 'en-US' ? 'en-US' : 'zh-CN'
}

void i18n.use(initReactI18next).init({
  resources,
  lng: typeof localStorage === 'undefined' ? 'zh-CN' : storedLocale(),
  fallbackLng: 'zh-CN',
  interpolation: { escapeValue: false },
})

export async function resetI18nForTests(): Promise<void> {
  await i18n.changeLanguage('zh-CN')
}

export default i18n
