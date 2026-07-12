import { getEntry } from 'astro:content';
import { z } from 'astro:content';

// === 各 YAML 文件的精确 schema ===
const siteSchema = z.object({
  name: z.string(),
  slogan: z.string(),
  slogan_zh: z.string(),
  description: z.string(),
  url: z.string().url(),
  email: z.string().email(),
  github: z.string().url(),
  avatar: z.string(),
  nav: z.array(z.object({
    label: z.string(),
    href: z.string(),
  })),
  footer: z.object({
    copyright: z.string(),
    links: z.array(z.object({
      label: z.string(),
      href: z.string(),
      external: z.boolean().default(false),
    })),
  }),
  seo: z.object({
    og_type: z.string(),
    theme_color: z.string(),
    keywords: z.array(z.string()),
  }),
});

const profileSchema = z.object({
  name: z.string(),
  role: z.string(),
  role_zh: z.string(),
  avatar: z.string(),
  bio: z.string(),
  bio_zh: z.string(),
  interests: z.array(z.string()),
  philosophy: z.array(z.string()),
  social: z.array(z.object({
    label: z.string(),
    href: z.string(),
    icon: z.string(),
  })),
  education: z.array(z.object({
    period: z.string(),
    school: z.string(),
    major: z.string(),
  })),
  future_direction: z.string(),
  contact_note: z.string(),
});

const currentlySchema = z.object({
  updated: z.coerce.date(),
  items: z.array(z.object({
    category: z.string(),
    content: z.string(),
  })),
});

const timelineSchema = z.object({
  events: z.array(z.object({
    date: z.string(),
    title: z.string(),
    category: z.string(),
    description: z.string(),
    tags: z.array(z.string()).default([]),
  })),
});

const skillsSchema = z.object({
  groups: z.array(z.object({
    category: z.string(),
    items: z.array(z.object({
      name: z.string(),
      level: z.number().min(1).max(5),
      note: z.string().optional(),
    })),
  })),
});

const gallerySchema = z.object({
  photos: z.array(z.object({
    src: z.string(),
    title: z.string(),
    location: z.string(),
    date: z.string(),
    description: z.string(),
  })),
});

// === 读取函数 ===
export async function getSiteConfig() {
  const entry = await getEntry('data', 'site');
  return siteSchema.parse(entry.data);
}

export async function getProfile() {
  const entry = await getEntry('data', 'about/profile');
  return profileSchema.parse(entry.data);
}

export async function getCurrently() {
  const entry = await getEntry('data', 'currently/currently');
  return currentlySchema.parse(entry.data);
}

export async function getTimeline() {
  const entry = await getEntry('data', 'timeline/timeline');
  return timelineSchema.parse(entry.data);
}

export async function getSkills() {
  const entry = await getEntry('data', 'skills/skills');
  return skillsSchema.parse(entry.data);
}

export async function getGallery() {
  const entry = await getEntry('data', 'gallery/gallery');
  return gallerySchema.parse(entry.data);
}
