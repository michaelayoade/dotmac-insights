/**
 * Global search hook for command palette
 * Searches across multiple entity types
 */

import { useState, useEffect, useMemo } from 'react';
import useSWR from 'swr';
import { fetchApi } from '@/lib/api';

export interface SearchResultItem {
  id: number | string;
  type: 'customer' | 'contact' | 'invoice' | 'ticket' | 'project' | 'order' | 'employee' | 'asset' | 'bill';
  title: string;
  subtitle?: string;
  href: string;
  status?: string;
  icon?: string;
}

export interface GlobalSearchResults {
  items: SearchResultItem[];
  total: number;
  query: string;
}

interface UseGlobalSearchOptions {
  debounceMs?: number;
  limit?: number;
  enabled?: boolean;
}

/**
 * Hook for global search across multiple entity types
 *
 * @example
 * const { results, isLoading, error, search, clearSearch } = useGlobalSearch();
 *
 * // Update search query
 * search('john');
 *
 * // Results will be debounced and fetched automatically
 */
export function useGlobalSearch(options: UseGlobalSearchOptions = {}) {
  const { debounceMs = 300, limit = 20, enabled = true } = options;
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Debounce the query
  useEffect(() => {
    if (!query) {
      setDebouncedQuery('');
      return;
    }

    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [query, debounceMs]);

  // Fetch search results
  const shouldFetch = enabled && debouncedQuery.length >= 2;

  const { data, isLoading, error, mutate } = useSWR<GlobalSearchResults>(
    shouldFetch ? ['global-search', debouncedQuery, limit] : null,
    async () => {
      // Call the search API endpoint
      const response = await fetchApi<{ results: SearchResultItem[]; total: number }>(
        `/search?q=${encodeURIComponent(debouncedQuery)}&limit=${limit}`
      );

      return {
        items: response.results || [],
        total: response.total || 0,
        query: debouncedQuery,
      };
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 1000,
    }
  );

  // Transform results into grouped sections
  const groupedResults = useMemo(() => {
    if (!data?.items) return {};

    const groups: Record<string, SearchResultItem[]> = {};
    data.items.forEach((item) => {
      const key = item.type;
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
    });

    return groups;
  }, [data]);

  const search = (newQuery: string) => {
    setQuery(newQuery);
  };

  const clearSearch = () => {
    setQuery('');
    setDebouncedQuery('');
  };

  return {
    query,
    debouncedQuery,
    results: data?.items || [],
    groupedResults,
    total: data?.total || 0,
    isLoading: isLoading || (query !== debouncedQuery && query.length >= 2),
    error,
    search,
    clearSearch,
    refetch: mutate,
  };
}

/**
 * Mock search function for development when backend is not available
 * This provides static navigation results and module links
 */
export function useMockGlobalSearch() {
  const [query, setQuery] = useState('');

  const results = useMemo(() => {
    if (!query || query.length < 2) return [];

    const lowerQuery = query.toLowerCase();

    // Static navigation items
    const navigationItems: SearchResultItem[] = [
      { id: 'nav-contacts', type: 'contact', title: 'Contacts', subtitle: 'Contact management', href: '/contacts' },
      { id: 'nav-sales', type: 'customer', title: 'Sales', subtitle: 'Invoices and orders', href: '/sales' },
      { id: 'nav-support', type: 'ticket', title: 'Support', subtitle: 'Helpdesk tickets', href: '/support' },
      { id: 'nav-hr', type: 'employee', title: 'People', subtitle: 'HR management', href: '/hr' },
      { id: 'nav-inventory', type: 'asset', title: 'Inventory', subtitle: 'Stock management', href: '/inventory' },
      { id: 'nav-projects', type: 'project', title: 'Projects', subtitle: 'Project management', href: '/projects' },
      { id: 'nav-field', type: 'order', title: 'Field Service', subtitle: 'Service orders', href: '/field-service' },
      { id: 'nav-books', type: 'invoice', title: 'Books', subtitle: 'Accounting', href: '/books' },
      { id: 'nav-assets', type: 'asset', title: 'Assets', subtitle: 'Fixed assets', href: '/assets' },
      { id: 'nav-purchasing', type: 'bill', title: 'Purchasing', subtitle: 'Bills and orders', href: '/purchasing' },
    ];

    return navigationItems.filter(
      (item) =>
        item.title.toLowerCase().includes(lowerQuery) ||
        item.subtitle?.toLowerCase().includes(lowerQuery)
    );
  }, [query]);

  return {
    query,
    results,
    isLoading: false,
    error: null,
    search: setQuery,
    clearSearch: () => setQuery(''),
  };
}
