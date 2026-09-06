import base from './playwright.config.mjs';
export default { ...base, outputDir: './execution-test-results', testMatch: '*.execution-browser.mjs', fullyParallel: false, workers: 1, maxFailures: 1 };
