import { describe, expect, it } from 'vitest';

import {
  characterGenderComparisonRequestSchema,
  multiFileUploadRequestSchema,
  projectControlPanelProjectListRequestSchema,
  projectCreateRequestSchema,
  projectModeSwitchRequestSchema,
  runConfigDiffRequestSchema,
  singleFileUploadRequestSchema,
} from '@/app/schemas/api';

describe('api request zod guards', () => {
  it('normalizes create-project payload and defaults storage flag', () => {
    const parsed = projectCreateRequestSchema.parse({
      title: '  Shadow Slave  ',
    });

    expect(parsed).toEqual({
      title: 'Shadow Slave',
      do_not_store_source_text: false,
    });
  });

  it('requires non-empty mode switch payload', () => {
    expect(() => projectModeSwitchRequestSchema.parse({ mode: '   ' })).toThrow();
    expect(projectModeSwitchRequestSchema.parse({ mode: 'audiobook' }).mode).toBe('audiobook');
  });

  it('validates control-panel list query params and enum filters', () => {
    const parsed = projectControlPanelProjectListRequestSchema.parse({
      page: 2,
      page_size: 20,
      status: 'running',
      last_run_status: 'failed',
      next_required_action: 'review_failure',
    });
    expect(parsed.page).toBe(2);
    expect(parsed.status).toBe('running');
    expect(() => projectControlPanelProjectListRequestSchema.parse({ last_run_status: 'stuck' })).toThrow();
  });

  it('defaults gender-comparison query params', () => {
    const parsed = characterGenderComparisonRequestSchema.parse({});
    expect(parsed.include_only_conflicts).toBe(false);
  });

  it('enforces positive run ids for config-diff query', () => {
    expect(() => runConfigDiffRequestSchema.parse({ base_run_id: 0, target_run_id: 2 })).toThrow();
    const parsed = runConfigDiffRequestSchema.parse({ base_run_id: 1, target_run_id: 2 });
    expect(parsed.target_run_id).toBe(2);
  });

  it('guards file upload payloads', () => {
    const chapterA = new File(['one'], '01.txt', { type: 'text/plain' });
    const chapterB = new File(['two'], '02.txt', { type: 'text/plain' });

    expect(singleFileUploadRequestSchema.parse({ file: chapterA }).file.name).toBe('01.txt');
    expect(multiFileUploadRequestSchema.parse({ files: [chapterA, chapterB] }).files).toHaveLength(2);
    expect(() => multiFileUploadRequestSchema.parse({ files: [] })).toThrow();
  });
});
