/**
 * Asset Settings Hooks
 * SWR hooks for fetching and updating asset settings.
 */
import useSWR, { SWRConfiguration } from 'swr';
import { useSWRConfig } from 'swr';
import { assetsApi, AssetSettings, AssetSettingsUpdate } from '@/lib/api/domains/assets';

/**
 * Hook to fetch asset settings
 */
export function useAssetSettings(
  params?: { company?: string },
  config?: SWRConfiguration
) {
  return useSWR<AssetSettings>(
    ['asset-settings', params?.company],
    () => assetsApi.getSettings(params?.company),
    config
  );
}

/**
 * Hook for asset settings mutations
 */
export function useAssetSettingsMutations() {
  const { mutate } = useSWRConfig();

  const updateSettings = async (
    updates: AssetSettingsUpdate,
    company?: string
  ): Promise<AssetSettings> => {
    const result = await assetsApi.updateSettings(updates, company);

    // Invalidate cache
    await mutate(['asset-settings', company]);

    return result;
  };

  return {
    updateSettings,
  };
}
