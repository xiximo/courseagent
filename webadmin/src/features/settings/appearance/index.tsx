import { useTranslation } from 'react-i18next'
import { ContentSection } from '../components/content-section'
import { AppearanceForm } from './appearance-form'

export function SettingsAppearance() {
  const { t } = useTranslation()
  return (
    <ContentSection
      title={t('settings.appearancePage.title')}
      desc={t('settings.appearancePage.desc')}
    >
      <AppearanceForm />
    </ContentSection>
  )
}
