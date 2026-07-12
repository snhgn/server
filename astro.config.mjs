import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkCallout from './src/plugins/remark-callout.mjs';

export default defineConfig({
  site: 'https://snhgn.me',
  trailingSlash: 'always',
  integrations: [mdx()],
  markdown: {
    syntaxHighlight: 'shiki',
    shikiConfig: { theme: 'github-dark' },
    remarkPlugins: [remarkMath, remarkCallout],
    rehypePlugins: [rehypeKatex],
  },
});
