import { defineCollection, z } from 'astro:content';

// === Markdown 集合 ===
const projects = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    status: z.enum(['shipped', 'in-progress', 'paused', 'archived']),
    year: z.number(),
    cover: z.string().optional(),
    tech: z.array(z.string()).default([]),
    github: z.string().url().or(z.literal('')).default(''),
    demo: z.string().url().or(z.literal('')).default(''),
    featured: z.boolean().default(false),
    order: z.number().default(99),
    description: z.string(),
    lessons: z.array(z.string()).default([]),
  }),
});

const learning = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    tags: z.array(z.string()).default([]),
    summary: z.string(),
    problems: z.array(z.string()).default([]),
    solutions: z.array(z.string()).default([]),
    next_steps: z.array(z.string()).default([]),
  }),
});

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    tags: z.array(z.string()).default([]),
    category: z.string().default('未分类'),
    description: z.string(),
    draft: z.boolean().default(false),
    reading_time: z.number().optional(),
  }),
});

// === YAML 数据集合(单独 schema 在 lib/content.ts 校验) ===
const data = defineCollection({
  type: 'data',
  schema: z.record(z.any()),
});

export const collections = { projects, learning, blog, data };
