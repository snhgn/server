import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import react from '@astrojs/react';
import node from '@astrojs/node';
import keystatic from '@keystatic/astro';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkCallout from './src/plugins/remark-callout.mjs';

export default defineConfig({
  site: 'https://snhgn.me',
  trailingSlash: 'always',
  output: 'hybrid',
  adapter: node({ mode: 'standalone' }),
  integrations: [react(), mdx(), keystatic()],
  markdown: {
    syntaxHighlight: 'shiki',
    shikiConfig: { theme: 'github-dark' },
    remarkPlugins: [remarkMath, remarkCallout],
    rehypePlugins: [rehypeKatex],
  },
});
