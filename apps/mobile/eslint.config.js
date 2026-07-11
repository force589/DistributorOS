const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ['.expo/*', 'coverage/*'],
    rules: {
      // TypeScript and Metro both verify module resolution. The ESLint import resolver
      // traverses above the workspace on sandboxed Windows and fails before linting.
      'import/no-unresolved': 'off',
    },
  },
]);
