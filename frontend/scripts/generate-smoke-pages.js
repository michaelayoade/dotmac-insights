#!/usr/bin/env node
/**
 * Auto-generate smoke-pages.ts from the actual page.tsx files in the app directory.
 *
 * Run from the frontend/ directory:
 *   node scripts/generate-smoke-pages.js > tests/e2e/fixtures/smoke-pages.ts
 */

const fs = require('fs');
const path = require('path');

const APP_DIR = path.join(__dirname, '..', 'app');

// Scope mappings by module
const MODULE_SCOPES = {
  'home': ['*'],
  'accounting': ['accounting:read'],
  'admin': ['admin:read', 'admin:write'],
  'analytics': ['analytics:read'],
  'assets': ['assets:read'],
  'banking': ['payments:read', 'openbanking:read'],
  'books': ['books:read'],
  'contacts': ['contacts:read'],
  'crm': ['crm:read'],
  'customers': ['customers:read'],
  'expense': ['expenses:read'],
  'expenses': ['expenses:read'],
  'explorer': ['explorer:read'],
  'field-service': ['field-service:read'],
  'fleet': ['fleet:read'],
  'hr': ['hr:read'],
  'inbox': ['inbox:read'],
  'insights': ['analytics:read'],
  'inventory': ['inventory:read'],
  'notifications': ['*'],
  'performance': ['performance:read'],
  'pops': ['*'],
  'projects': ['projects:read'],
  'purchasing': ['purchasing:read'],
  'reports': ['reports:read'],
  'sales': ['sales:read'],
  'support': ['support:read'],
  'sync': ['sync:read'],
  'tasks': ['*'],
};

function findPageFiles(dir, basePath = '') {
  const pages = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    const routePath = path.join(basePath, entry.name);

    if (entry.isDirectory()) {
      pages.push(...findPageFiles(fullPath, routePath));
    } else if (entry.name === 'page.tsx') {
      // Convert filesystem path to route
      const route = basePath.replace(/\\/g, '/') || '/';
      pages.push(route.startsWith('/') ? route : '/' + route);
    }
  }

  return pages;
}

function getModuleName(route) {
  if (route === '/') return 'home';
  const parts = route.split('/').filter(Boolean);
  return parts[0] || 'home';
}

function formatRouteName(route) {
  if (route === '/') return 'Home';

  const parts = route.split('/').filter(Boolean);
  return parts
    .map(part => {
      if (part.startsWith('[') && part.endsWith(']')) {
        return part.slice(1, -1).toUpperCase();
      }
      return part.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    })
    .join(' / ');
}

// Find all pages
const allRoutes = findPageFiles(APP_DIR).sort();

// Group by module
const modulePages = {};
for (const route of allRoutes) {
  const module = getModuleName(route);
  if (!modulePages[module]) {
    modulePages[module] = [];
  }
  modulePages[module].push(route);
}

// Generate TypeScript output
console.log(`/**
 * Auto-generated smoke test page definitions.
 * Generated on: ${new Date().toISOString()}
 *
 * To regenerate: node scripts/generate-smoke-pages.js > tests/e2e/fixtures/smoke-pages.ts
 */

import type { Scope } from './auth';

export interface PageConfig {
  path: string;
  name: string;
  scopes: Scope[];
  skipReason?: string;
}

export const MODULE_SCOPES: Record<string, Scope[]> = ${JSON.stringify(MODULE_SCOPES, null, 2).replace(/"(\w+)":/g, "'$1':").replace(/"/g, "'")};

export const SMOKE_PAGES: Record<string, PageConfig[]> = {`);

const modules = Object.keys(modulePages).sort();
for (let i = 0; i < modules.length; i++) {
  const module = modules[i];
  const pages = modulePages[module];

  console.log(`  '${module}': [`);
  for (const page of pages) {
    const name = formatRouteName(page);
    console.log(`    { path: '${page}', name: '${name}', scopes: MODULE_SCOPES['${module}'] || ['*'] },`);
  }
  console.log(`  ],`);
}

console.log(`};

/**
 * Get all pages as a flat array
 */
export function getAllPages(): PageConfig[] {
  return Object.values(SMOKE_PAGES).flat();
}

/**
 * Get static pages only (no dynamic [id] routes)
 */
export function getStaticPages(): PageConfig[] {
  return getAllPages().filter(p => !p.path.includes('['));
}

/**
 * Get page count
 */
export function getPageCount(): { total: number; static: number; dynamic: number } {
  const all = getAllPages();
  const staticPages = all.filter(p => !p.path.includes('['));
  return {
    total: all.length,
    static: staticPages.length,
    dynamic: all.length - staticPages.length,
  };
}
`);
