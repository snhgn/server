import { config, fields, collection, singleton } from '@keystatic/core';

// Storage mode: local for dev, github for production
const storage = process.env.NODE_ENV === 'production'
  ? {
      kind: 'github',
      repo: {
        owner: process.env.GITHUB_REPO_OWNER || 'snhgn',
        name: process.env.GITHUB_REPO_NAME || 'snhgn.me',
      },
    }
  : { kind: 'local' };

export default config({
  storage,
  collections: {
    blog: collection({
      label: 'Blog',
      slugField: 'title',
      path: 'src/content/blog/*/',
      format: { contentField: 'content' },
      entryLayout: 'content',
      schema: {
        title: fields.slug({ name: { label: 'Title' } }),
        date: fields.date({ label: 'Date', validation: { isRequired: true } }),
        description: fields.text({ label: 'Description', validation: { isRequired: true } }),
        tags: fields.array(fields.text({ label: 'Tag' }), {
          label: 'Tags',
          itemLabel: (p) => p.value,
        }),
        category: fields.text({ label: 'Category', defaultValue: '未分类' }),
        draft: fields.checkbox({ label: 'Draft', defaultValue: false }),
        content: fields.mdx({ label: 'Content' }),
      },
    }),

    learning: collection({
      label: 'Learning',
      slugField: 'title',
      path: 'src/content/learning/*/',
      format: { contentField: 'content' },
      entryLayout: 'content',
      schema: {
        title: fields.slug({ name: { label: 'Title' } }),
        date: fields.date({ label: 'Date', validation: { isRequired: true } }),
        summary: fields.text({ label: 'Summary', validation: { isRequired: true } }),
        tags: fields.array(fields.text({ label: 'Tag' }), {
          label: 'Tags',
          itemLabel: (p) => p.value,
        }),
        problems: fields.array(fields.text({ label: 'Problem' }), {
          label: 'Problems',
          itemLabel: (p) => p.value,
        }),
        solutions: fields.array(fields.text({ label: 'Solution' }), {
          label: 'Solutions',
          itemLabel: (p) => p.value,
        }),
        next_steps: fields.array(fields.text({ label: 'Next Step' }), {
          label: 'Next Steps',
          itemLabel: (p) => p.value,
        }),
        content: fields.mdx({ label: 'Content' }),
      },
    }),

    projects: collection({
      label: 'Projects',
      slugField: 'title',
      path: 'src/content/projects/*/',
      format: { contentField: 'content' },
      entryLayout: 'content',
      schema: {
        title: fields.slug({ name: { label: 'Title' } }),
        date: fields.date({ label: 'Date', validation: { isRequired: true } }),
        description: fields.text({ label: 'Description', validation: { isRequired: true } }),
        status: fields.select({
          label: 'Status',
          options: [
            { label: 'Shipped', value: 'shipped' },
            { label: 'In Progress', value: 'in-progress' },
            { label: 'Paused', value: 'paused' },
            { label: 'Archived', value: 'archived' },
          ],
          defaultValue: 'in-progress',
        }),
        year: fields.integer({ label: 'Year', validation: { isRequired: true } }),
        cover: fields.text({ label: 'Cover Image Path' }),
        tech: fields.array(fields.text({ label: 'Tech' }), {
          label: 'Tech Stack',
          itemLabel: (p) => p.value,
        }),
        github: fields.url({ label: 'GitHub URL' }),
        demo: fields.url({ label: 'Demo URL' }),
        featured: fields.checkbox({ label: 'Featured', defaultValue: false }),
        order: fields.integer({ label: 'Order', defaultValue: 99 }),
        lessons: fields.array(fields.text({ label: 'Lesson' }), {
          label: 'Lessons',
          itemLabel: (p) => p.value,
        }),
        content: fields.mdx({ label: 'Content' }),
      },
    }),
  },
  singletons: {
    site: singleton({
      label: 'Site Config',
      path: 'src/content/data/site',
      format: { data: 'yaml' },
      schema: {
        name: fields.text({ label: 'Site Name', validation: { isRequired: true } }),
        slogan: fields.text({ label: 'Slogan (EN)' }),
        slogan_zh: fields.text({ label: 'Slogan (ZH)' }),
        description: fields.text({ label: 'Description', multiline: true }),
        url: fields.url({ label: 'Site URL' }),
        email: fields.text({ label: 'Email' }),
        github: fields.url({ label: 'GitHub URL' }),
        avatar: fields.text({ label: 'Avatar Path' }),
        nav: fields.array(
          fields.object({
            label: fields.text({ label: 'Label' }),
            href: fields.text({ label: 'URL' }),
          }),
          { label: 'Navigation', itemLabel: (p) => p.fields.label.value }
        ),
        footer: fields.object({
          label: 'Footer',
          fields: {
            copyright: fields.text({ label: 'Copyright' }),
            links: fields.array(
              fields.object({
                label: fields.text({ label: 'Label' }),
                href: fields.text({ label: 'URL' }),
                external: fields.checkbox({ label: 'External', defaultValue: false }),
              }),
              { label: 'Links', itemLabel: (p) => p.fields.label.value }
            ),
          },
        }),
        seo: fields.object({
          label: 'SEO',
          fields: {
            og_type: fields.text({ label: 'OG Type' }),
            theme_color: fields.text({ label: 'Theme Color' }),
            keywords: fields.array(fields.text({ label: 'Keyword' }), {
              label: 'Keywords',
              itemLabel: (p) => p.value,
            }),
          },
        }),
      },
    }),

    about: singleton({
      label: 'About',
      path: 'src/content/data/about/profile',
      format: { data: 'yaml' },
      schema: {
        name: fields.text({ label: 'Name', validation: { isRequired: true } }),
        role: fields.text({ label: 'Role (EN)' }),
        role_zh: fields.text({ label: 'Role (ZH)' }),
        avatar: fields.text({ label: 'Avatar Path' }),
        bio: fields.text({ label: 'Bio (EN)', multiline: true }),
        bio_zh: fields.text({ label: 'Bio (ZH)', multiline: true }),
        interests: fields.array(fields.text({ label: 'Interest' }), {
          label: 'Interests',
          itemLabel: (p) => p.value,
        }),
        philosophy: fields.array(fields.text({ label: 'Philosophy', multiline: true }), {
          label: 'Philosophy',
          itemLabel: (p) => p.value.slice(0, 40) + '...',
        }),
        social: fields.array(
          fields.object({
            label: fields.text({ label: 'Label' }),
            href: fields.text({ label: 'URL' }),
            icon: fields.text({ label: 'Icon' }),
          }),
          { label: 'Social Links', itemLabel: (p) => p.fields.label.value }
        ),
        education: fields.array(
          fields.object({
            period: fields.text({ label: 'Period' }),
            school: fields.text({ label: 'School' }),
            major: fields.text({ label: 'Major' }),
          }),
          { label: 'Education', itemLabel: (p) => p.fields.school.value }
        ),
        future_direction: fields.text({ label: 'Future Direction', multiline: true }),
        contact_note: fields.text({ label: 'Contact Note', multiline: true }),
      },
    }),

    currently: singleton({
      label: 'Currently',
      path: 'src/content/data/currently/currently',
      format: { data: 'yaml' },
      schema: {
        updated: fields.date({ label: 'Last Updated' }),
        items: fields.array(
          fields.object({
            category: fields.text({ label: 'Category' }),
            content: fields.text({ label: 'Content', multiline: true }),
          }),
          { label: 'Items', itemLabel: (p) => p.fields.category.value }
        ),
      },
    }),

    timeline: singleton({
      label: 'Timeline',
      path: 'src/content/data/timeline/timeline',
      format: { data: 'yaml' },
      schema: {
        events: fields.array(
          fields.object({
            date: fields.text({ label: 'Date' }),
            title: fields.text({ label: 'Title' }),
            category: fields.text({ label: 'Category' }),
            description: fields.text({ label: 'Description', multiline: true }),
            tags: fields.array(fields.text({ label: 'Tag' }), {
              label: 'Tags',
              itemLabel: (p) => p.value,
            }),
          }),
          { label: 'Events', itemLabel: (p) => p.fields.title.value }
        ),
      },
    }),

    skills: singleton({
      label: 'Skills',
      path: 'src/content/data/skills/skills',
      format: { data: 'yaml' },
      schema: {
        groups: fields.array(
          fields.object({
            category: fields.text({ label: 'Category' }),
            items: fields.array(
              fields.object({
                name: fields.text({ label: 'Name' }),
                level: fields.integer({ label: 'Level (1-5)', defaultValue: 3 }),
                note: fields.text({ label: 'Note' }),
              }),
              { label: 'Skills', itemLabel: (p) => p.fields.name.value }
            ),
          }),
          { label: 'Groups', itemLabel: (p) => p.fields.category.value }
        ),
      },
    }),

    gallery: singleton({
      label: 'Gallery',
      path: 'src/content/data/gallery/gallery',
      format: { data: 'yaml' },
      schema: {
        photos: fields.array(
          fields.object({
            src: fields.text({ label: 'Image Path' }),
            title: fields.text({ label: 'Title' }),
            location: fields.text({ label: 'Location' }),
            date: fields.text({ label: 'Date' }),
            description: fields.text({ label: 'Description', multiline: true }),
          }),
          { label: 'Photos', itemLabel: (p) => p.fields.title.value }
        ),
      },
    }),
  },
});
