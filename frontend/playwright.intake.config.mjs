import base from './playwright.config.mjs';
export default { ...base, outputDir: './intake-test-results', testMatch: '*.intake-browser.mjs', fullyParallel: false, workers: 1, maxFailures: 1 };
