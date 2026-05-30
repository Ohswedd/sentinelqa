// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// SentinelQA documentation site.
// - Authority: see docs/adr/0032-docs-site.md for the choice of Astro Starlight.
// - Status labels: every feature page sets `status` in its frontmatter; the
//   per-page status badge is rendered by src/components/StatusBadge.astro and
//   surfaced via the custom override in src/overrides/PageFrame.astro.
// - All content lives under src/content/docs/; the sidebar below tracks the
//   nav contract in plans/phase-27-docs-and-adrs/01-docs-site.md.
// - Output is a fully static site under apps/docs/dist/ — no runtime server
//   is required to view the docs.

export default defineConfig({
  site: 'https://sentinelqa.dev',
  outDir: './dist',
  integrations: [
    starlight({
      title: 'SentinelQA',
      description:
        'Playwright-native release-confidence engine for LLM-built and human-built software.',
      logo: {
        src: './src/assets/logo.svg',
        replacesTitle: false,
      },
      social: {
        github: 'https://github.com/Ohswedd/sentinelqa',
      },
      editLink: {
        baseUrl: 'https://github.com/Ohswedd/sentinelqa/edit/main/apps/docs/',
      },
      lastUpdated: false,
      customCss: ['./src/styles/custom.css'],
      components: {
        PageFrame: './src/overrides/PageFrame.astro',
      },
      sidebar: [
        {
          label: 'Get Started',
          items: [
            { label: 'Install', link: '/get-started/install/' },
            { label: 'Quickstart', link: '/get-started/quickstart/' },
            { label: 'Run your first audit', link: '/get-started/first-audit/' },
            { label: 'Doctor', link: '/get-started/doctor/' },
          ],
        },
        {
          label: 'Concepts',
          items: [
            { label: 'Architecture', link: '/concepts/architecture/' },
            { label: 'Safety boundary', link: '/concepts/safety-boundary/' },
            { label: 'Run lifecycle', link: '/concepts/run-lifecycle/' },
          ],
        },
        {
          label: 'CLI Reference',
          items: [{ label: 'Overview', link: '/cli/' }],
        },
        {
          label: 'SDK Reference',
          items: [{ label: 'Overview', link: '/sdk/' }],
        },
        {
          label: 'MCP Reference',
          items: [{ label: 'Overview', link: '/mcp/' }],
        },
        {
          label: 'Modules',
          items: [
            { label: 'Overview', link: '/modules/' },
            { label: 'Discovery', link: '/modules/discovery/' },
            { label: 'Planner', link: '/modules/planner/' },
            { label: 'Generator', link: '/modules/generator/' },
            { label: 'Runner', link: '/modules/runner/' },
            { label: 'Analyzer', link: '/modules/analyzer/' },
            { label: 'Functional', link: '/modules/functional/' },
            { label: 'Accessibility', link: '/modules/accessibility/' },
            { label: 'Performance', link: '/modules/performance/' },
            { label: 'Security', link: '/modules/security/' },
            { label: 'LLM-Code Audit', link: '/modules/llm-audit/' },
            { label: 'Healer', link: '/modules/healer/' },
            { label: 'Visual', link: '/modules/visual/' },
            { label: 'API', link: '/modules/api/' },
            { label: 'Chaos', link: '/modules/chaos/' },
          ],
        },
        {
          label: 'Plugins',
          items: [{ label: 'Developer guide', link: '/plugins/' }],
        },
        {
          label: 'Integrations',
          items: [{ label: 'Overview', link: '/integrations/' }],
        },
        {
          label: 'CI/CD',
          items: [{ label: 'Overview', link: '/cicd/' }],
        },
        {
          label: 'Error Codes',
          items: [{ label: 'Reference', link: '/errors/' }],
        },
        {
          label: 'Security & Safety',
          items: [{ label: 'Overview', link: '/security-and-safety/' }],
        },
        {
          label: 'ADRs',
          items: [{ label: 'Index', link: '/adrs/' }],
        },
        {
          label: 'Contributing',
          items: [{ label: 'Overview', link: '/contributing/' }],
        },
      ],
    }),
  ],
});
