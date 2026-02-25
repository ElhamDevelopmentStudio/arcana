import { z } from 'zod';

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url().default('http://localhost:8000'),
  VITE_FEATURE_SCRAPE_ENABLED: z
    .enum(['true', 'false'])
    .default('false')
    .transform((value) => value === 'true'),
});

const parsedEnv = envSchema.safeParse({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
  VITE_FEATURE_SCRAPE_ENABLED: import.meta.env.VITE_FEATURE_SCRAPE_ENABLED,
});

if (!parsedEnv.success) {
  const flattened = parsedEnv.error.flatten();
  throw new Error(`Invalid frontend env configuration: ${JSON.stringify(flattened.fieldErrors)}`);
}

export const appEnv = {
  apiBaseUrl: parsedEnv.data.VITE_API_BASE_URL,
  featureScrapeEnabled: parsedEnv.data.VITE_FEATURE_SCRAPE_ENABLED,
};
