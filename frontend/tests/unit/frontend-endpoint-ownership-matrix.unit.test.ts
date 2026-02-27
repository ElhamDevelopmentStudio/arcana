import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

type EndpointOwnershipRow = {
  endpoint: string;
  routeOwners: string;
  hookOwner: string;
  componentOwners: string;
  testOwners: string;
  status: string;
};

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(currentDir, '../../..');
const ownershipMatrixPath = path.resolve(repoRoot, 'docs/frontend_endpoint_ownership_matrix.md');

function stripMarkdownTicks(value: string) {
  return value.replace(/^`/, '').replace(/`$/, '').trim();
}

function parseEndpointOwnershipRows(markdown: string): EndpointOwnershipRow[] {
  return markdown
    .split('\n')
    .filter((line) => line.startsWith('| `'))
    .map((line) => {
      const cells = line
        .split('|')
        .slice(1, -1)
        .map((cell) => stripMarkdownTicks(cell.trim()));

      if (cells.length !== 6) {
        throw new Error(`Unexpected matrix row format: ${line}`);
      }

      const [endpoint, routeOwners, hookOwner, componentOwners, testOwners, status] = cells;
      return {
        endpoint,
        routeOwners,
        hookOwner,
        componentOwners,
        testOwners,
        status,
      };
    });
}

function extractTestPaths(testOwners: string) {
  return testOwners
    .split(',')
    .map((entry) => stripMarkdownTicks(entry.trim()))
    .filter((entry) => entry.startsWith('frontend/tests/'));
}

describe('frontend endpoint ownership matrix regression guard', () => {
  it('keeps every frontend-consumed endpoint fully assigned with explicit test ownership', () => {
    const matrixMarkdown = readFileSync(ownershipMatrixPath, 'utf8');
    const rows = parseEndpointOwnershipRows(matrixMarkdown);

    expect(rows.length).toBeGreaterThan(0);

    const nonAssignedRows = rows
      .filter((row) => row.status !== 'assigned')
      .map((row) => `${row.endpoint} => ${row.status}`);
    expect(nonAssignedRows).toEqual([]);

    const missingOwnershipRows = rows
      .filter((row) => /unassigned|missing dedicated/i.test(row.testOwners))
      .map((row) => `${row.endpoint} => ${row.testOwners}`);
    expect(missingOwnershipRows).toEqual([]);
  });

  it('references existing frontend test artifacts for each endpoint row', () => {
    const matrixMarkdown = readFileSync(ownershipMatrixPath, 'utf8');
    const rows = parseEndpointOwnershipRows(matrixMarkdown);

    const missingArtifacts: string[] = [];

    for (const row of rows) {
      const testPaths = extractTestPaths(row.testOwners);
      if (testPaths.length === 0) {
        missingArtifacts.push(`${row.endpoint} => no frontend test paths listed`);
        continue;
      }
      for (const testPath of testPaths) {
        const absolutePath = path.resolve(repoRoot, testPath);
        if (!existsSync(absolutePath)) {
          missingArtifacts.push(`${row.endpoint} => missing test file ${testPath}`);
        }
      }
    }

    expect(missingArtifacts).toEqual([]);
  });
});
