import { defineCollection, z } from 'astro:content';
import { docsSchema } from '@astrojs/starlight/schema';

// Starlight 0.28 expects content collections at src/content/config.ts.
// Every SentinelQA feature page declares a `status` frontmatter field
// taking one of `Planned | Experimental | Stable | Deprecated`
// (docs/dev/status-labels.md). The field is optional at the schema
// level so meta pages (landing, ADR index) can omit it; the Python CI
// guard in tests/integration/docs/test_status_labels.py fails the
// build if any feature page lacks the field.
export const collections = {
  docs: defineCollection({
    schema: docsSchema({
      extend: z.object({
        status: z.enum(['Planned', 'Experimental', 'Stable', 'Deprecated']).optional(),
      }),
    }),
  }),
};
