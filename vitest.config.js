import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'happy-dom',
    globals: true,
    include: ['static/tests/**/*.test.js'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json'],
      include: ['static/modules/**/*.js', 'static/core/**/*.js'],
      exclude: ['static/tests/**', 'static/**/*.test.js']
    }
  }
});
