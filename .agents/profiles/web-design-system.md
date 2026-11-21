# Profile: Web / design system
- Design tokens: one JSON source (`tokens/*.json`, e.g. W3C Design Tokens format); CSS/TS outputs are generated, never hand-edited (put them in `protected_globs`).
- Components: one folder per component (`Component.tsx`, `Component.test.tsx`, `Component.stories.tsx`). A component folder is one ticket's ownership unit.
- Contracts: TypeScript prop types in `docs/ai/contracts/components.d.ts`.
- Gates: `tsc --noEmit`, `eslint .`, `prettier --check .`, `vitest run`, Storybook build.
- Tester gate: visual snapshot tests (Storybook test runner / Playwright screenshots) + automated accessibility checks.
- Lock resources: `package.json`, lockfile, `tokens/**`, theme provider.
- `.gitignore`: `node_modules/ dist/ storybook-static/ coverage/`
