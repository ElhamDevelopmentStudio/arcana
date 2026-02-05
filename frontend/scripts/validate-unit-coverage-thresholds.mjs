import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { pathToFileURL } from 'node:url';

function normalizeModuleKey(moduleKey) {
  const normalized = String(moduleKey ?? '').trim().replaceAll('\\', '/').replace(/^\.\//, '');
  return normalized;
}

function normalizeCoveragePath(filePath, baseDir = process.cwd()) {
  const normalizedInput = String(filePath ?? '').trim().replaceAll('\\', '/');
  if (!normalizedInput) {
    return '';
  }
  const relativePath = path.isAbsolute(normalizedInput)
    ? path.relative(baseDir, normalizedInput).replaceAll('\\', '/')
    : normalizedInput;
  return relativePath.replace(/^\.\//, '');
}

function buildModuleMatcher(moduleKey) {
  const normalizedModuleKey = normalizeModuleKey(moduleKey);
  const isExactFile = /\.[a-z0-9]+$/i.test(normalizedModuleKey);
  if (isExactFile) {
    return (filePath) => filePath === normalizedModuleKey;
  }
  const modulePrefix = normalizedModuleKey.endsWith('/') ? normalizedModuleKey : `${normalizedModuleKey}/`;
  return (filePath) => filePath.startsWith(modulePrefix);
}

export function evaluateCoverageThresholds(coverageSummary, moduleThresholds, baseDir = process.cwd()) {
  const coverageEntries = Object.entries(coverageSummary ?? {})
    .filter(([key, value]) => key !== 'total' && value && typeof value === 'object')
    .map(([filePath, value]) => ({
      filePath: normalizeCoveragePath(filePath, baseDir),
      linesCovered: Number(value?.lines?.covered ?? 0),
      linesTotal: Number(value?.lines?.total ?? 0),
    }))
    .filter((entry) => entry.filePath.length > 0 && Number.isFinite(entry.linesCovered) && Number.isFinite(entry.linesTotal));

  return Object.entries(moduleThresholds ?? {}).map(([moduleKey, rawThreshold]) => {
    const threshold = Number(rawThreshold);
    const matcher = buildModuleMatcher(moduleKey);
    const matchingEntries = coverageEntries.filter((entry) => matcher(entry.filePath));
    const coveredLines = matchingEntries.reduce((sum, entry) => sum + entry.linesCovered, 0);
    const totalLines = matchingEntries.reduce((sum, entry) => sum + entry.linesTotal, 0);
    const coveragePercent = totalLines > 0 ? (coveredLines / totalLines) * 100 : 0;
    const passed = totalLines > 0 && coveragePercent >= threshold;
    return {
      module: normalizeModuleKey(moduleKey),
      threshold,
      coveragePercent: Number(coveragePercent.toFixed(2)),
      coveredLines,
      totalLines,
      matchedFiles: matchingEntries.map((entry) => entry.filePath),
      passed,
      reason: totalLines > 0 ? (passed ? 'ok' : 'below_threshold') : 'no_matching_files',
    };
  });
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

function loadModuleThresholds(thresholdsPath) {
  const payload = readJson(thresholdsPath);
  if (!payload || typeof payload !== 'object' || !payload.modules || typeof payload.modules !== 'object') {
    throw new Error("Thresholds file must contain a 'modules' object.");
  }

  const normalizedThresholds = {};
  for (const [moduleKey, rawThreshold] of Object.entries(payload.modules)) {
    const normalizedModuleKey = normalizeModuleKey(moduleKey);
    const threshold = Number(rawThreshold);
    if (!normalizedModuleKey) {
      throw new Error('Module keys must not be blank.');
    }
    if (!Number.isFinite(threshold) || threshold < 0 || threshold > 100) {
      throw new Error(`Threshold for '${normalizedModuleKey}' must be a number between 0 and 100.`);
    }
    normalizedThresholds[normalizedModuleKey] = threshold;
  }
  return normalizedThresholds;
}

export function runCoverageThresholdValidation({
  coverageSummaryPath = path.resolve(process.cwd(), 'coverage/coverage-summary.json'),
  thresholdsPath = path.resolve(process.cwd(), 'unit_coverage_thresholds.json'),
  baseDir = process.cwd(),
} = {}) {
  const coverageSummary = readJson(coverageSummaryPath);
  const moduleThresholds = loadModuleThresholds(thresholdsPath);
  const results = evaluateCoverageThresholds(coverageSummary, moduleThresholds, baseDir);
  const failures = results.filter((result) => !result.passed);

  for (const result of results) {
    const status = result.passed ? 'PASS' : 'FAIL';
    console.log(
      `[${status}] ${result.module}: ${result.coveragePercent.toFixed(2)}% `
      + `(threshold ${result.threshold.toFixed(2)}%, lines ${result.coveredLines}/${result.totalLines})`,
    );
  }

  if (failures.length > 0) {
    console.error('Unit coverage threshold validation failed.');
  } else {
    console.log('Unit coverage threshold validation passed.');
  }

  return {
    results,
    failures,
  };
}

const isMainModule = process.argv[1]
  ? import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
  : false;

if (isMainModule) {
  const coverageSummaryPath = process.argv[2]
    ? path.resolve(process.cwd(), process.argv[2])
    : path.resolve(process.cwd(), 'coverage/coverage-summary.json');
  const thresholdsPath = process.argv[3]
    ? path.resolve(process.cwd(), process.argv[3])
    : path.resolve(process.cwd(), 'unit_coverage_thresholds.json');

  const { failures } = runCoverageThresholdValidation({
    coverageSummaryPath,
    thresholdsPath,
    baseDir: process.cwd(),
  });
  process.exitCode = failures.length > 0 ? 1 : 0;
}
